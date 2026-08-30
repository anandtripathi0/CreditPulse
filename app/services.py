import os
import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "ml_pipeline", "saved_models")


try:
    model = joblib.load(os.path.join(MODEL_DIR, "xgboost_model.pkl"))
    scaler = joblib.load(os.path.join(MODEL_DIR, "scaler.pkl"))
    le_edu = joblib.load(os.path.join(MODEL_DIR, "le_edu.pkl"))
    ohe = joblib.load(os.path.join(MODEL_DIR, "ohe.pkl"))
    model_columns = joblib.load(os.path.join(MODEL_DIR, "model_columns.pkl"))
    print("All ML artifacts loaded successfully in services.py!")
except Exception as e:
    print(f"Error loading ML artifacts: {e}")


def get_loan_prediction(data_dict: dict):
    """Takes input dictionary from frontend form, applies the exact preprocessing

    pipeline, and returns (status, probability).
    """
    df = pd.DataFrame([data_dict])

    numerical_cols = [
        "Applicant_Income",
        "Coapplicant_Income",
        "Age",
        "Dependents",
        "Credit_Score",
        "Existing_Loans",
        "DTI_Ratio",
        "Savings",
        "Collateral_Value",
        "Loan_Amount",
        "Loan_Term",
    ]

    df[numerical_cols] = scaler.transform(df[numerical_cols])

    try:
        df["Education_Level"] = le_edu.transform(df["Education_Level"])
    except Exception:
        df["Education_Level"] = 0

    ohe_cols = [
        "Employment_Status",
        "Marital_Status",
        "Loan_Purpose",
        "Property_Area",
        "Gender",
        "Employer_Category",
    ]
    encoded_array = ohe.transform(df[ohe_cols])
    encoded_df = pd.DataFrame(
        encoded_array,
        columns=ohe.get_feature_names_out(ohe_cols),
        index=df.index,
    )

    final_df = pd.concat([df.drop(columns=ohe_cols), encoded_df], axis=1)

    final_df = final_df.reindex(columns=model_columns, fill_value=0)

    prediction = model.predict(final_df)[0]
    probability = model.predict_proba(final_df)[0][1]

    status = "Approved" if int(prediction) == 1 else "Rejected"

    return status, float(probability)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

def generate_loan_advice(user_message: str, applicant_data: dict, status: str, probability: float) -> str:
    """
    Generates dynamic, conversational, and complete financial advice using Gemini.
    """
    system_prompt = f"""
    You are 'CreditPulse Advisor', an expert AI Loan Underwriter.
    
    Current Application Context:
    - Status: {status} (Confidence: {round(probability * 100, 2)}%)
    - Monthly Income: ₹{applicant_data.get('Applicant_Income')}
    - Credit Score: {applicant_data.get('Credit_Score')}
    - DTI Ratio: {applicant_data.get('DTI_Ratio')}
    - Loan Amount Requested: ₹{applicant_data.get('Loan_Amount')}
    
    STRICT RULES FOR YOUR RESPONSE:
    1. CONVERSATIONAL: If the user simply says "Hi", "Hello", or "Good morning", reply kindly and ask: "Hello! How can I assist you with your {status} loan application today?" DO NOT start explaining the loan status unless asked.
    2. DIRECT & HELPFUL: If they ask why they were rejected, pinpoint the exact weak metrics (like low credit score or high DTI) and give 3 actionable steps to fix it.
    3. NO CUT-OFFS: Complete your sentences. Provide structured answers using bullet points for readability.
    4. PROFESSIONAL TONE: Be empathetic but realistic.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,           
            max_output_tokens=2048,    
        )
    )

    return response.text