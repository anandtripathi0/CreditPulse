from enum import Enum
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class EmploymentStatus(str, Enum):
    SALARIED = "Salaried"
    SELF_EMPLOYED = "Self-Employed"
    UNEMPLOYED = "Unemployed"


class PropertyArea(str, Enum):
    URBAN = "Urban"
    SEMIURBAN = "Semiurban"
    RURAL = "Rural"

class VisitorData(BaseModel):
    ip_address: str
    consent_status: str

class LoanApplicationInput(BaseModel):
    Applicant_Income: float = Field(..., ge=0, example=50000.0)
    Coapplicant_Income: float = Field(default=0.0, ge=0, example=15000.0)
    Age: int = Field(..., ge=18, le=100, example=28)
    Dependents: int = Field(default=0, ge=0, example=1)
    Credit_Score: float = Field(..., ge=300, le=900, example=750.0)
    Existing_Loans: int = Field(default=0, ge=0, example=0)
    DTI_Ratio: float = Field(
        ..., ge=0.0, le=100.0, example=25.5
    )  # Debt-to-Income
    Savings: float = Field(default=0.0, ge=0, example=120000.0)
    Collateral_Value: float = Field(default=0.0, ge=0, example=500000.0)
    Loan_Amount: float = Field(..., gt=0, example=250000.0)
    Loan_Term: float = Field(
        ..., gt=0, example=36.0
    )  

    Employment_Status: EmploymentStatus
    Marital_Status: str = Field(..., example="Single")
    Loan_Purpose: str = Field(..., example="Home")
    Property_Area: PropertyArea
    Education_Level: str = Field(..., example="Graduate")
    Gender: str = Field(..., example="Male")
    Employer_Category: str = Field(..., example="Private")


class LoanPredictionOutput(BaseModel):
    status: str = Field(
        ..., example="Approved"
    )  
    probability: float = Field(
        ..., ge=0.0, le=1.0, example=0.87
    )  

class ChatRequest(BaseModel):
    user_message: str
    applicant_data: Dict[str, Any]
    status: str
    probability: float

class ChatResponse(BaseModel):
    reply: str

# auth

class OTPRequest(BaseModel):
    email: EmailStr

class VerifySignup(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=15)
    password: str = Field(..., min_length=8, max_length=128)
    otp: str = Field(..., min_length=6, max_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class ResetPassword(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

# Credit Profile

class CreditProfileCreate(BaseModel):
    credit_limit: float = Field(..., gt=0, le=10000000, example=100000)

class CreditProfileUpdate(BaseModel):
    credit_limit: Optional[float] = Field(None, gt=0, le=10000000)
    used_credit: Optional[float] = Field(None, ge=0)

class CreditTransaction(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=200)
    category: str = Field(default="General")

class PurchaseSimulation(BaseModel):
    amount: float = Field(..., gt=0)

class ChangePassword(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

class TwoFactorConfirm(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)

class TwoFactorDisable(BaseModel):
    password: str = Field(..., min_length=1)

class TwoFactorLoginVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

# Credit Score Predictor
class CreditScoreInput(BaseModel):
    active_loans: int = Field(default=0, ge=0, le=50)
    total_loan_amount: float = Field(default=0.0, ge=0.0)
    outstanding_balance: float = Field(default=0.0, ge=0.0)
    loan_types: Optional[Any] = Field(default_factory=list)
    credit_age_years: Optional[float] = Field(default=2.0)
    credit_history_months: Optional[int] = Field(default=24)
    
    total_emis_due: int = Field(default=12, ge=0, le=600)
    emis_paid_on_time: int = Field(default=12, ge=0, le=600)
    emis_paid_late: int = Field(default=0, ge=0, le=600)
    missed_emis: int = Field(default=0, ge=0, le=600)
    avg_delay_days: Optional[int] = Field(default=0)
    average_delay_days: Optional[float] = Field(default=0.0)
    
    credit_limit: float = Field(default=100000.0, ge=0.0)
    credit_utilized: float = Field(default=20000.0, ge=0.0)
    monthly_income: float = Field(default=50000.0, ge=0.0)
    employment_type: Optional[str] = Field(default="Salaried")
    savings_balance: Optional[float] = Field(default=50000.0)
    dti_ratio: Optional[float] = Field(default=25.0)