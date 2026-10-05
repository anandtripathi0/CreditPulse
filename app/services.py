import os
import hashlib
import secrets
import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError

from app.config import (
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    SENDER_EMAIL, SENDER_PASSWORD, OTP_EXPIRY_MINUTES
)

# ==========================================
# AUTHENTICATION SERVICES
# ==========================================

import bcrypt

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# ==========================================
# OTP SERVICES (Secure)
# ==========================================

def generate_otp():
    """Generate a cryptographically random 6-digit OTP."""
    return str(secrets.randbelow(900000) + 100000)

def hash_otp(otp: str) -> str:
    """Hash OTP with SHA-256 for secure storage."""
    return hashlib.sha256(otp.encode()).hexdigest()

def verify_otp_hash(plain_otp: str, hashed_otp: str) -> bool:
    """Verify a plaintext OTP against its hash."""
    return hashlib.sha256(plain_otp.encode()).hexdigest() == hashed_otp

# ==========================================
# EMAIL SERVICES
# ==========================================

def _build_otp_email_html(otp: str, purpose: str, user_name: str = "") -> str:
    """Build a professional HTML email template for OTP."""
    purpose_title = "Verify Your Account" if purpose == "signup" else "Reset Your Password"
    purpose_desc = (
        "to complete your account registration" if purpose == "signup" 
        else "to reset your password"
    )
    greeting = f"Hi {user_name}," if user_name else "Hello,"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="margin:0;padding:0;font-family:'Inter',Arial,sans-serif;background-color:#F4F7F5;">
      <div style="max-width:480px;margin:40px auto;background:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(46,90,68,0.1);">
        <div style="background:#2E5A44;padding:32px;text-align:center;">
          <h1 style="color:#FFFFFF;margin:0;font-size:24px;letter-spacing:-0.5px;">CreditPulse</h1>
          <p style="color:#DDE7E1;margin:8px 0 0;font-size:13px;">{purpose_title}</p>
        </div>
        <div style="padding:32px;">
          <p style="color:#1F2E26;font-size:15px;margin:0 0 16px;">{greeting}</p>
          <p style="color:#5C6E64;font-size:14px;line-height:1.6;margin:0 0 24px;">
            Use the following verification code {purpose_desc}. This code expires in <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.
          </p>
          <div style="background:#F4F7F5;border:2px dashed #2E5A44;border-radius:12px;padding:20px;text-align:center;margin:0 0 24px;">
            <span style="font-size:32px;font-weight:800;letter-spacing:8px;color:#2E5A44;">{otp}</span>
          </div>
          <div style="background:#FFF8F0;border-left:4px solid #E07A5F;padding:12px 16px;border-radius:0 8px 8px 0;margin:0 0 24px;">
            <p style="color:#1F2E26;font-size:12px;margin:0;">
              <strong>⚠️ Security Notice:</strong> Never share this code with anyone. CreditPulse will never ask for your OTP via phone or chat.
            </p>
          </div>
          <p style="color:#5C6E64;font-size:12px;margin:0;">If you didn't request this, please ignore this email.</p>
        </div>
        <div style="background:#F4F7F5;padding:16px;text-align:center;border-top:1px solid #E2E8E4;">
          <p style="color:#5C6E64;font-size:11px;margin:0;">&copy; 2026 CreditPulse Financial Analytics. All rights reserved.</p>
        </div>
      </div>
    </body>
    </html>
    """

class EmailConfigurationError(Exception):
    pass

class EmailDeliveryError(Exception):
    pass

def send_otp_email(receiver_email: str, otp: str, purpose: str, user_name: str = ""):
    """Send OTP via Gmail SMTP with professional HTML template."""
    import logging
    
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logging.error("Email credentials (SENDER_EMAIL, SENDER_PASSWORD) not configured in environment variables.")
        raise EmailConfigurationError("Email service is not configured")

    subject = (
        "CreditPulse — Verify Your Account" if purpose == "signup"
        else "CreditPulse — Reset Your Password"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"CreditPulse <{SENDER_EMAIL}>"
    msg["To"] = receiver_email

    # Plain text fallback
    text_content = (
        f"Your CreditPulse {purpose} OTP is: {otp}\n"
        f"It is valid for {OTP_EXPIRY_MINUTES} minutes.\n"
        f"Do not share this with anyone."
    )
    html_content = _build_otp_email_html(otp, purpose, user_name)

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(
                SENDER_EMAIL.strip(),
                SENDER_PASSWORD.strip().replace(" ", "")
            )
            server.send_message(msg)
        logging.info("OTP email sent successfully to %s", receiver_email)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logging.error(
            "Gmail SMTP authentication failed. "
            "Check SENDER_EMAIL and Gmail App Password."
        )
        logging.error("SMTP error code: %s", getattr(e, "smtp_code", None))

        raise EmailDeliveryError(
            "Gmail authentication failed. "
            "Check the sender email and Gmail App Password."
        )

    except (smtplib.SMTPConnectError, TimeoutError) as e:
        logging.exception("Could not connect to Gmail SMTP.")
        raise EmailDeliveryError(
            "Could not connect to Gmail email service."
        )

    except Exception:
        logging.exception("Unexpected error while sending OTP email.")
        raise EmailDeliveryError(
            "Failed to send OTP email. Please try again."
        )

# ==========================================
# CREDIT PROFILE SERVICES
# ==========================================

# Predefined purchase categories with items and price ranges
PURCHASE_CATEGORIES = [
    {
        "category": "Electronics",
        "icon": "💻",
        "items": [
            {"name": "Wireless Earbuds", "price": 2500},
            {"name": "Smartwatch", "price": 8000},
            {"name": "Smartphone", "price": 25000},
            {"name": "Tablet", "price": 35000},
            {"name": "Laptop", "price": 55000},
            {"name": "Gaming Console", "price": 45000},
            {"name": "4K Television", "price": 65000},
            {"name": "DSLR Camera", "price": 80000},
        ]
    },
    {
        "category": "Travel",
        "icon": "✈️",
        "items": [
            {"name": "Weekend Getaway", "price": 5000},
            {"name": "Domestic Flight", "price": 8000},
            {"name": "Hotel Stay (3 nights)", "price": 15000},
            {"name": "International Trip", "price": 75000},
            {"name": "Luxury Vacation", "price": 150000},
        ]
    },
    {
        "category": "Shopping",
        "icon": "🛍️",
        "items": [
            {"name": "Clothing & Accessories", "price": 5000},
            {"name": "Designer Shoes", "price": 12000},
            {"name": "Premium Watch", "price": 30000},
            {"name": "Designer Handbag", "price": 45000},
            {"name": "Luxury Jewelry", "price": 80000},
        ]
    },
    {
        "category": "Home & Lifestyle",
        "icon": "🏠",
        "items": [
            {"name": "Home Decor Set", "price": 8000},
            {"name": "Kitchen Appliance", "price": 15000},
            {"name": "Smart Home Setup", "price": 25000},
            {"name": "Furniture Set", "price": 50000},
            {"name": "Home Renovation", "price": 200000},
        ]
    },
    {
        "category": "Education",
        "icon": "📚",
        "items": [
            {"name": "Online Course", "price": 3000},
            {"name": "Certification Program", "price": 15000},
            {"name": "Professional Workshop", "price": 25000},
            {"name": "Semester Fees", "price": 60000},
        ]
    },
    {
        "category": "Fitness & Wellness",
        "icon": "💪",
        "items": [
            {"name": "Gym Membership (Annual)", "price": 15000},
            {"name": "Sports Equipment", "price": 10000},
            {"name": "Health Checkup Package", "price": 8000},
            {"name": "Premium Fitness Gear", "price": 25000},
        ]
    },
    {
        "category": "Dining & Entertainment",
        "icon": "🍽️",
        "items": [
            {"name": "Fine Dining (2 people)", "price": 5000},
            {"name": "Concert Tickets", "price": 8000},
            {"name": "Monthly Food Subscription", "price": 3000},
            {"name": "Event Party", "price": 20000},
        ]
    },
]


def get_what_can_i_buy(available_credit: float) -> list:
    """Generate purchase suggestions based on available credit with affordability labels."""
    results = []
    for cat in PURCHASE_CATEGORIES:
        cat_items = []
        for item in cat["items"]:
            price = item["price"]
            utilization_pct = (price / available_credit * 100) if available_credit > 0 else 100
            
            if price <= available_credit * 0.7:
                status = "affordable"
                status_label = "Fits within your available credit"
            elif price <= available_credit:
                status = "near_limit"
                status_label = f"Would use ~{utilization_pct:.0f}% of your available credit"
            else:
                status = "over_limit"
                status_label = "Exceeds your current available credit"
            
            cat_items.append({
                "name": item["name"],
                "price": price,
                "status": status,
                "status_label": status_label,
                "utilization_pct": round(utilization_pct, 1)
            })
        
        results.append({
            "category": cat["category"],
            "icon": cat["icon"],
            "items": cat_items
        })
    
    return results


def simulate_purchase(credit_limit: float, used_credit: float, purchase_amount: float) -> dict:
    """Simulate a purchase and return impact analysis."""
    available_before = credit_limit - used_credit
    fits = purchase_amount <= available_before
    
    new_used = used_credit + purchase_amount
    remaining = available_before - purchase_amount
    current_utilization = (used_credit / credit_limit * 100) if credit_limit > 0 else 0
    new_utilization = (new_used / credit_limit * 100) if credit_limit > 0 else 0
    
    if not fits:
        over_by = purchase_amount - available_before
        warning = f"This purchase exceeds your available credit by ₹{over_by:,.0f}"
    elif new_utilization > 75:
        warning = "This purchase would push your credit utilization above 75%, which may impact your credit score"
    elif new_utilization > 50:
        warning = "This purchase would use more than half of your total credit limit"
    else:
        warning = None
    
    return {
        "fits_within_credit": fits,
        "purchase_amount": purchase_amount,
        "available_before": round(available_before, 2),
        "remaining_after": round(max(remaining, 0), 2),
        "current_utilization": round(current_utilization, 1),
        "new_utilization": round(min(new_utilization, 100), 1),
        "warning": warning,
        "disclaimer": "This is an estimate only and does not represent an actual transaction."
    }


# ==========================================
# ML PREDICTION SERVICES
# ==========================================

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

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if os.getenv("GEMINI_API_KEY") else None

def generate_loan_advice(user_message: str, applicant_data: dict, status: str, probability: float) -> str:
    """
    Generates dynamic, conversational, and complete financial advice using Gemini.
    """
    if client is None:
        return "The AI advisor is not configured yet. You can still use Credit Studio to calculate repayments, compare loan costs, and plan your budget."
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


# ==========================================
# CREDIT SCORE PREDICTOR ENGINE
# ==========================================

def calculate_credit_score_estimate(data: dict) -> dict:
    """
    Centralized, deterministic credit-score estimation algorithm (300-900).
    Considers payment history, credit utilization, debt exposure, credit age, and loan mix.
    """
    emis_due = max(1, int(data.get('total_emis_due', 12)))
    emis_on_time = min(emis_due, max(0, int(data.get('emis_paid_on_time', emis_due))))
    emis_late = max(0, int(data.get('emis_paid_late', 0)))
    missed = max(0, int(data.get('missed_emis', 0)))
    avg_delay = max(0, int(data.get('avg_delay_days') or data.get('average_delay_days') or 0))
    
    # 1. Payment history (0 - 250 pts)
    on_time_ratio = emis_on_time / emis_due
    payment_pts = on_time_ratio * 240.0
    payment_pts -= (missed * 40.0)
    payment_pts -= (emis_late * 15.0)
    payment_pts -= min(25.0, avg_delay * 0.5)
    payment_pts = max(0.0, min(250.0, payment_pts))
    
    # 2. Credit Utilization (0 - 170 pts)
    limit = max(0.0, float(data.get('credit_limit', 0)))
    utilized = max(0.0, float(data.get('credit_utilized', 0)))
    util_pct = (utilized / limit * 100.0) if limit > 0 else 20.0
    if util_pct <= 10.0:
        util_pts = 170.0
    elif util_pct <= 30.0:
        util_pts = 150.0
    elif util_pct <= 50.0:
        util_pts = 110.0
    elif util_pct <= 75.0:
        util_pts = 60.0
    else:
        util_pts = 20.0
        
    # 3. Debt Exposure / DTI (0 - 90 pts)
    dti = max(0.0, float(data.get('dti_ratio', 25.0)))
    if dti <= 20.0:
        dti_pts = 90.0
    elif dti <= 35.0:
        dti_pts = 75.0
    elif dti <= 50.0:
        dti_pts = 50.0
    else:
        dti_pts = 20.0
        
    # 4. History Age (0 - 50 pts)
    months = data.get('credit_history_months')
    if (months is None or months == 0) and 'credit_age_years' in data:
        months = int(float(data.get('credit_age_years', 2)) * 12)
    months = max(1, int(months or 24))
    if months >= 60:
        age_pts = 50.0
    elif months >= 36:
        age_pts = 40.0
    elif months >= 18:
        age_pts = 30.0
    elif months >= 6:
        age_pts = 20.0
    else:
        age_pts = 10.0
        
    # 5. Loan Mix (0 - 40 pts)
    loan_types = data.get('loan_types', [])
    if isinstance(loan_types, str):
        loan_types = [lt.strip() for lt in loan_types.split(',') if lt.strip()]
    unique_types = len(set(loan_types))
    if unique_types >= 2:
        mix_pts = 40.0
    elif unique_types == 1:
        mix_pts = 28.0
    else:
        mix_pts = 25.0
        
    total_pts = payment_pts + util_pts + dti_pts + age_pts + mix_pts
    final_score = int(min(900, max(300, round(300 + total_pts))))
    
    # Risk Band
    if final_score >= 780:
        risk_band = "Excellent"
        rating_color = "#10B981"
    elif final_score >= 720:
        risk_band = "Good"
        rating_color = "#2E5A44"
    elif final_score >= 660:
        risk_band = "Fair"
        rating_color = "#F59E0B"
    elif final_score >= 600:
        risk_band = "Needs Attention"
        rating_color = "#F97316"
    else:
        risk_band = "High Risk"
        rating_color = "#EF4444"
        
    # Factor breakdown
    factors = {
        "payment_history": {
            "name": "Payment History",
            "status": "Strong" if payment_pts >= 200 else ("Moderate" if payment_pts >= 120 else "Needs Attention"),
            "score_pts": round(payment_pts, 1),
            "max_pts": 250,
            "detail": f"{emis_on_time}/{emis_due} EMIs on-time ({int(on_time_ratio * 100)}%)"
        },
        "credit_utilization": {
            "name": "Credit Utilization",
            "status": "Optimal" if util_pct <= 30 else ("Moderate" if util_pct <= 50 else "High"),
            "score_pts": round(util_pts, 1),
            "max_pts": 170,
            "detail": f"{util_pct:.1f}% utilized of ₹{limit:,.0f} limit" if limit > 0 else "No revolving card limit"
        },
        "debt_exposure": {
            "name": "Debt Exposure & DTI",
            "status": "Low" if dti <= 25 else ("Balanced" if dti <= 45 else "Heavy"),
            "score_pts": round(dti_pts, 1),
            "max_pts": 90,
            "detail": f"{dti:.1f}% Debt-to-Income ratio"
        },
        "credit_age": {
            "name": "Credit History Age",
            "status": "Mature" if months >= 36 else ("Developing" if months >= 12 else "Thin File"),
            "score_pts": round(age_pts, 1),
            "max_pts": 50,
            "detail": f"{months} months credit experience"
        },
        "loan_mix": {
            "name": "Credit Mix",
            "status": "Diversified" if unique_types >= 2 else "Standard",
            "score_pts": round(mix_pts, 1),
            "max_pts": 40,
            "detail": f"{unique_types} distinct credit line(s)"
        }
    }
    
    # Recommendations
    what_helped = []
    if missed == 0:
        what_helped.append("Flawless track record with zero missed EMI payments.")
    if emis_late == 0 and emis_on_time > 0:
        what_helped.append("100% on-time repayment consistency across all active loan obligations.")
    if util_pct <= 30.0 and limit > 0:
        what_helped.append(f"Prudent credit card utilization ({util_pct:.1f}%), safely below the 30% advisory threshold.")
    if dti <= 35.0:
        what_helped.append(f"Comfortable Debt-to-Income ratio ({dti:.1f}%), indicating strong disposable buffer.")
    if months >= 36:
        what_helped.append(f"Long-standing borrowing history spanning {months // 12} years.")
    if unique_types >= 2:
        what_helped.append("Healthy mix of diverse credit facilities.")
    if not what_helped:
        what_helped.append("Active profile with ongoing verifiable financial history.")
        
    what_reduced = []
    if missed > 0:
        what_reduced.append(f"{missed} missed or defaulted EMI payment(s) creating severe delinquency risk flags.")
    if emis_late > 0:
        what_reduced.append(f"{emis_late} late EMI payment(s) recorded with an average delay of {avg_delay} days.")
    if util_pct > 30.0:
        what_reduced.append(f"Credit card utilization is elevated at {util_pct:.1f}% (recommended benchmark is under 30%).")
    if dti > 40.0:
        what_reduced.append(f"High Debt-to-Income ratio of {dti:.1f}%, leaving limited debt capacity.")
    if months < 18:
        what_reduced.append("Relatively short credit history, limiting longitudinal credit reliability data.")
    if not what_reduced:
        what_reduced.append("No critical negative flags detected in current submission.")
        
    how_to_improve = []
    if util_pct > 30.0:
        how_to_improve.append("Pay down revolving credit card balances below 30% of your limit prior to monthly statement generation.")
    if emis_late > 0 or missed > 0:
        how_to_improve.append("Set up NACH / auto-debit mandates to ensure upcoming loan EMIs are automatically cleared on due dates.")
    if dti > 40.0:
        how_to_improve.append("Avoid taking on new loans or BNPL debt for 6 months; focus on amortizing existing high-interest obligations.")
    if months < 36:
        how_to_improve.append("Keep existing credit cards and older accounts active to build average credit account age over time.")
    if unique_types < 2 and months >= 24:
        how_to_improve.append("Maintain a balanced mix of secured and unsecured credit lines as your financial profile grows.")
    if not how_to_improve:
        how_to_improve.append("Continue regular on-time repayments and maintain low card utilization to preserve your top-tier score.")
        
    return {
        "estimated_score": final_score,
        "max_score": 900,
        "min_score": 300,
        "risk_band": risk_band,
        "rating_color": rating_color,
        "factors": factors,
        "what_helped": what_helped,
        "what_reduced": what_reduced,
        "how_to_improve": how_to_improve,
        "disclaimer": "This is an educational estimate based on the information you provide and is not an official credit bureau score."
    }
