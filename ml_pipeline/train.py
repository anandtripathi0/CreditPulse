import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score,classification_report


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_PATH = os.path.join(BASE_DIR, "..", "dataset", "preprocessed_data.csv")

def train_model():
    print("Loading processed dataset...")
    df = pd.read_csv(PROCESSED_DATA_PATH)

    X = df.drop(columns=["Loan_Approved"])
    y = df["Loan_Approved"]

    X_train,X_test,y_train,y_test = train_test_split(
        X,y,random_state=42,
        test_size=0.2,
        stratify=y
    )

    # model training
    print("Training XGBoost Model...")
    model = XGBClassifier(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
    model.fit(X_train,y_train)

    y_pred = model.predict(X_test)
    print("\n--- Model Evaluation ---")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print("\nClassification Report:")

    print(classification_report(y_test,y_pred))

    print("\nSaving trained model to 'saved_models/'...")
    joblib.dump(model, "saved_models/xgboost_model.pkl")
    print("Model saved successfully!")

if __name__ == "__main__":
    train_model()