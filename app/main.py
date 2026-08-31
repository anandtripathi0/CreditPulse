import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, Request,Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from fastapi import HTTPException

from app.schemas import LoanApplicationInput,ChatRequest,ChatResponse,VisitorData
from app.services import get_loan_prediction,generate_loan_advice
from app.database import application_collection


app = FastAPI(title="CreditWise Loan System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="home.html"
    )


@app.post("/api/predict")
async def predict_loan(application: LoanApplicationInput):
    
    data = application.model_dump()

    status, prob = await asyncio.to_thread(get_loan_prediction, data)

    record = {
        "applicant_data": data,
        "prediction": {
            "status": status,
            "probability": prob,
        },
        "created_at": datetime.now(timezone.utc),
    }
    await application_collection.insert_one(record)

    return {"status": status, "probability": prob}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):

    cursor = application_collection.find().sort("created_at", -1).limit(50)
    raw_applications = await cursor.to_list(length=50)

    applications = []
    for doc in raw_applications:
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
            doc["created_at"] = doc["created_at"].isoformat()
        applications.append(doc)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"applications": applications}
    )


@app.get("/result", response_class=HTMLResponse)
async def view_result(request: Request, status: str = "Rejected", prob: float = 0.0):
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"status": status, "probability": prob},
    )

@app.post("/api/chat",response_model=ChatResponse)
async def chat_with_advisor(payload:ChatRequest):
    reply = generate_loan_advice(
        user_message=payload.user_message,
        applicant_data=payload.applicant_data,
        status=payload.status,
        probability=payload.probability
    )
    return ChatResponse(reply=reply)

@app.get("/record/{record_id}", response_class=HTMLResponse)
async def view_single_record(request: Request, record_id: str):
    
    try:
        # Fetch data based on MongoDB ID
        record = await application_collection.find_one({"_id": ObjectId(record_id)})
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        
        # Format the date
        if "created_at" in record and hasattr(record["created_at"], "isoformat"):
            record["created_at"] = record["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            
        record["_id"] = str(record["_id"])
        
        return templates.TemplateResponse(
            request=request,
            name="record_detail.html",
            context={"record": record}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid Record ID")

@app.get("/help-center", response_class=HTMLResponse)
async def help_center(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="help_center.html"
    )

@app.get("/application",response_class = HTMLResponse)
async def home(request:Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.post("/api/save-visitor")
async def vistors(data:VisitorData):
    record = {
        "ip_address":data.ip_address,
        "consent_status":data.consent_status,
        "visited_at":datetime.now(timezone.utc)
    }
    await application_collection.database["visitors"].insert_one(record)
    return {"status": "success", "message": "IP Saved to Database"}