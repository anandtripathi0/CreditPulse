from enum import Enum
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional  
from datetime import datetime,timezone

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