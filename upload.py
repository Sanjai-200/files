"""
upload.py

Minimal test tool: pick ONE .xlsx or .json file via a native file
dialog, read its contents, and upload each row/object as a separate
document to the Firestore "knowledge" collection.

Usage:
    python upload.py
"""

import json
import os
import sys

import pandas as pd
from tkinter import Tk, filedialog

from firebase_config import get_firestore_client

COLLECTION_NAME = "knowledge"


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


def upload_records(db, records, source_filename, file_type):
    """Upload each record as a separate document to the collection."""
    collection_ref = db.collection(COLLECTION_NAME)
    uploaded_count = 0
    errors = []

    for i, record in enumerate(records):
        doc_data = dict(record)  # copy so we don't mutate the original
        doc_data["source"] = source_filename
        doc_data["file_type"] = file_type

        try:
            collection_ref.add(doc_data)  # auto-generated document ID
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
    print(f"Records found: {len(records)}")

    # 4. Upload to Firestore
    print(f"Uploading to Firestore collection '{COLLECTION_NAME}'...")
    try:
        uploaded_count, errors = upload_records(db, records, filename, file_type)
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


if __name__ == "__main__":
    main()
