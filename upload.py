"""
upload.py

Minimal test tool: pick ONE .xlsx or .json file via a native file
dialog, read its contents, and upload each row/object as a separate
document to a Firestore collection named after the file itself.

Duplicate protection (two layers):
  1. File-level: a hash of the file's full content is stored in a
     small "_uploads_registry" collection. If the same file
     (same name + same content) is selected again, the upload is
     skipped entirely.
  2. Row-level: each document's ID is a deterministic hash of that
     row's content, instead of an auto-generated ID. So even if the
     file changed slightly and the registry check is bypassed,
     re-uploading identical rows overwrites the same document
     instead of creating a duplicate.

Usage:
    python upload.py
"""

import hashlib
import json
import os
import re
import sys

import pandas as pd
from tkinter import Tk, filedialog

from firebase_config import get_firestore_client

REGISTRY_COLLECTION = "_uploads_registry"


def select_file():
    """Open a native file picker restricted to .xlsx and .json files.

    Returns the selected file path, or None if the user cancelled.
    """
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)  # bring dialog to front

    file_path = filedialog.askopenfilename(
        title="Select an Excel (.xlsx) or JSON (.json) file",
        filetypes=[
            ("Excel and JSON files", "*.xlsx *.json"),
            ("Excel files", "*.xlsx"),
            ("JSON files", "*.json"),
        ],
    )

    root.destroy()
    return file_path or None


def sanitize_collection_name(filename):
    """Turn a filename into a safe Firestore collection name.

    Uses the filename without its extension. Firestore collection
    IDs can't contain '/' and shouldn't start with '.', so we strip
    unsafe characters and fall back to underscores.
    """
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r"[^A-Za-z0-9_\-]", "_", stem).strip("._")
    if not stem:
        stem = "unnamed_collection"
    return stem


def hash_bytes(data: bytes) -> str:
    """Return a stable sha256 hex digest for a chunk of bytes."""
    return hashlib.sha256(data).hexdigest()


def hash_record(record: dict) -> str:
    """Return a stable hash for a single row/object's content.

    Keys are sorted and values are JSON-serialized so the same
    logical row always produces the same ID, regardless of dict
    ordering or how it was loaded (Excel vs JSON).
    """
    normalized = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def get_file_hash(file_path):
    """Compute a sha256 hash of the raw file contents."""
    with open(file_path, "rb") as f:
        return hash_bytes(f.read())


def check_already_uploaded(db, collection_name, file_hash):
    """Check the registry for a previous upload of this exact file.

    Returns True if this collection was already populated from a
    file with the same content hash (i.e. a true duplicate upload).
    """
    doc = db.collection(REGISTRY_COLLECTION).document(collection_name).get()
    if not doc.exists:
        return False
    data = doc.to_dict() or {}
    return data.get("file_hash") == file_hash


def update_registry(db, collection_name, filename, file_hash, record_count):
    """Record that this file has now been uploaded into the registry."""
    db.collection(REGISTRY_COLLECTION).document(collection_name).set(
        {
            "source_filename": filename,
            "file_hash": file_hash,
            "record_count": record_count,
        }
    )


def load_excel_records(file_path):
    """Read an .xlsx file and return a list of dicts (one per row)."""
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}") from e

    if df.empty:
        raise ValueError("The Excel file is empty (no rows found).")

    # Drop fully-empty rows, replace NaN with None so Firestore accepts it
    df = df.dropna(how="all")
    df = df.where(pd.notnull(df), None)

    records = df.to_dict(orient="records")
    if not records:
        raise ValueError("No usable rows found in the Excel file.")

    return records


def load_json_records(file_path):
    """Read a .json file and return a list of dicts.

    Accepts either:
      - a JSON array of objects: [ {...}, {...} ]
      - a single JSON object:    { ... }
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON file: {e}") from e
    except Exception as e:
        raise ValueError(f"Could not read JSON file: {e}") from e

    if isinstance(data, list):
        records = [item for item in data if isinstance(item, dict)]
        if not records:
            raise ValueError("JSON array contains no valid objects.")
    elif isinstance(data, dict):
        if not data:
            raise ValueError("JSON object is empty.")
        records = [data]
    else:
        raise ValueError(
            "Unsupported JSON structure. Expected an object or an array of objects."
        )

    return records


def upload_records(db, records, collection_name, source_filename, file_type):
    """Upload each record as a document in the file's own collection.

    Each document ID is a deterministic hash of the row's own
    content, so uploading the exact same row again just overwrites
    the same document instead of creating a duplicate.
    """
    collection_ref = db.collection(collection_name)
    uploaded_count = 0
    errors = []

    for i, record in enumerate(records):
        doc_data = dict(record)  # copy so we don't mutate the original
        doc_data["source"] = source_filename
        doc_data["file_type"] = file_type

        doc_id = hash_record(record)

        try:
            collection_ref.document(doc_id).set(doc_data)  # deterministic ID, no dupes
            uploaded_count += 1
        except Exception as e:
            errors.append(f"Row/object {i + 1}: {e}")

    return uploaded_count, errors


def main():
    print("=== Firebase Firestore Upload Test ===")

    # 1. Connect to Firestore first (fail fast if credentials are bad)
    try:
        db = get_firestore_client()
    except Exception as e:
        print(f"[ERROR] Firebase connection failed: {e}")
        sys.exit(1)

    # 2. Let the user pick a file
    file_path = select_file()
    if not file_path:
        print("No file selected. Operation cancelled.")
        sys.exit(0)

    filename = os.path.basename(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    collection_name = sanitize_collection_name(filename)

    # 3. Parse the file based on its extension
    try:
        if ext == ".xlsx":
            records = load_excel_records(file_path)
            file_type = "excel"
        elif ext == ".json":
            records = load_json_records(file_path)
            file_type = "json"
        else:
            print(f"[ERROR] Unsupported file type: {ext}. Please select .xlsx or .json.")
            sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print(f"Selected file: {filename}")
    print(f"Detected type: {file_type}")
    print(f"Target collection: {collection_name}")
    print(f"Records found: {len(records)}")

    # 3b. Skip if this exact file (same name + same content) was
    #     already uploaded before — prevents duplicate-file uploads.
    file_hash = get_file_hash(file_path)
    if check_already_uploaded(db, collection_name, file_hash):
        print(
            f"[SKIPPED] '{filename}' has already been uploaded to "
            f"'{collection_name}' with identical content. No changes made."
        )
        sys.exit(0)

    # 4. Upload to Firestore
    print(f"Uploading to Firestore collection '{collection_name}'...")
    try:
        uploaded_count, errors = upload_records(
            db, records, collection_name, filename, file_type
        )
    except Exception as e:
        print(f"[ERROR] Unexpected upload failure: {e}")
        sys.exit(1)

    # 5. Report results
    print("\n=== Upload Summary ===")
    print(f"Successfully uploaded: {uploaded_count} document(s)")

    if errors:
        print(f"Failed: {len(errors)} document(s)")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("All records uploaded successfully.")
        # Only mark the file as "seen" once every row succeeded, so a
        # partially-failed upload can still be retried later.
        update_registry(db, collection_name, filename, file_hash, uploaded_count)


if __name__ == "__main__":
    main()
