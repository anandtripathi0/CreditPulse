import numpy as np
import pandas as pd
import joblib
import os
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder,OneHotEncoder,StandardScaler


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATASET_PATH = os.path.join(BASE_DIR, "..", "dataset", "loan_approval_data.csv")
PROCESSED_DATA_PATH = os.path.join(BASE_DIR, "..", "dataset", "preprocessed_data.csv")
MODEL_DIRS = os.path.join(BASE_DIR, "saved_models")

def run_preprocessing():
    print("1. Loading raw dataset..")
    df = pd.read_csv(RAW_DATASET_PATH)

    if 'Applicant_ID' in df.columns:
        df = df.drop(columns=['Applicant_ID'])

    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
    numerical_cols = df.select_dtypes(include=['number']).columns.tolist()

    print("2. Handeling missing values..")
    num_imp = SimpleImputer(strategy="mean")
    df[numerical_cols] = num_imp.fit_transform(df[numerical_cols])

    cate_imp = SimpleImputer(strategy='most_frequent')
    df[categorical_cols] = cate_imp.fit_transform(df[categorical_cols])

    print("3. Scaling numerical features...")
    scaler = StandardScaler()
    df[numerical_cols] = scaler.fit_transform(df[numerical_cols])

    print("4. Applying label encoding...")
    le_edu = LabelEncoder()
    le_target = LabelEncoder()

    df["Education_Level"] = le_edu.fit_transform(df["Education_Level"])
    df["Loan_Approved"] = le_target.fit_transform(df["Loan_Approved"])

    print("5. Applying one-hot encoding...")
    ohe_cols = ["Employment_Status", "Marital_Status", "Loan_Purpose", "Property_Area", "Gender", "Employer_Category"]

    ohe = OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")
    encoded_data = ohe.fit_transform(df[ohe_cols])

    encoded_df = pd.DataFrame(encoded_data,columns=ohe.get_feature_names_out(ohe_cols),index=df.index)
    df = pd.concat([df.drop(columns=ohe_cols), encoded_df], axis=1)

    print("6. saving preprocessing artifact(.pkl files)..")
    os.makedirs(MODEL_DIRS,exist_ok=True)

    joblib.dump(num_imp,f"{MODEL_DIRS}/num_imputer.pkl")
    joblib.dump(cate_imp,f"{MODEL_DIRS}/cate_imputer.pkl")
    joblib.dump(scaler, f"{MODEL_DIRS}/scaler.pkl")
    joblib.dump(le_edu,f"{MODEL_DIRS}/le_edu.pkl")
    joblib.dump(ohe,f"{MODEL_DIRS}/ohe.pkl")


    feature_columns = df.drop(columns=['Loan_Approved']).columns.tolist()
    joblib.dump(feature_columns, f"{MODEL_DIRS}/model_columns.pkl")

    print(f"7. Saving processed dataset to {PROCESSED_DATA_PATH}...")
    df.to_csv(PROCESSED_DATA_PATH, index=False)

    print("Preprocessing completed successfully!")

if __name__ == "__main__":
    run_preprocessing()