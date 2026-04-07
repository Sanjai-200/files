import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pickle

# LOAD DATASET
df = pd.read_csv("dataset.csv")

print("Dataset loaded successfully!\n")
print(df.head())

# 🔥 COUNT RISK VALUES
print("\nRisk Count:")
print(df["risk"].value_counts())

# PREPARE DATA
X = df[["device", "location", "loginCount", "hour", "failedAttempts"]]
y = df["risk"]

# SPLIT DATA
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# TRAIN MODEL
model = RandomForestClassifier()
model.fit(X_train, y_train)

# CHECK ACCURACY
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("\nAccuracy:", accuracy)

# 🔥 OPTIONAL TEST (can remove later)
print("\nTesting model...")

test_safe = [[1, 0, 1, 10, 0]]
test_risk = [[1, 1, 10, 2, 5]]

print("Safe Test →", model.predict(test_safe)[0])
print("Risk Test →", model.predict(test_risk)[0])

# 🔥 SAVE MODEL (IMPORTANT)
with open("model.pkl", "wb") as f:
    pickle.dump(model, f)

print("\n✅ Model saved as model.pkl")