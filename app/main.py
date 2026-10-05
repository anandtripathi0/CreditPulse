import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import FastAPI, Request, Cookie, Depends, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from bson import ObjectId

from app.schemas import (
    LoanApplicationInput, ChatRequest, ChatResponse, VisitorData,
    OTPRequest, VerifySignup, ResetPassword, UserLogin,
    CreditProfileCreate, CreditProfileUpdate, CreditTransaction, PurchaseSimulation,
    ChangePassword, CreditScoreInput,
    TwoFactorConfirm, TwoFactorDisable, TwoFactorLoginVerify
)
from app.services import (
    get_loan_prediction, generate_loan_advice,
    generate_otp, send_otp_email, get_password_hash, verify_password,
    create_access_token, decode_access_token, hash_otp, verify_otp_hash,
    get_what_can_i_buy, simulate_purchase, calculate_credit_score_estimate,
    EmailConfigurationError, EmailDeliveryError
)
from app.database import (
    users_collection, user_profiles_collection, credit_evaluations_collection,
    credit_score_history_collection, user_activity_collection,
    credit_profiles_collection, otps_collection, application_collection
)
from app.config import OTP_EXPIRY_MINUTES, OTP_RESEND_COOLDOWN_SECONDS, OTP_MAX_ATTEMPTS


app = FastAPI(title="CreditPulse - Multi-User Credit Analytics System")

from app.credit_tools import router as credit_tools_router
app.include_router(credit_tools_router)


@app.get("/credit-tools", response_class=HTMLResponse)
async def credit_tools_page(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(request=request, name="credit_tools.html", context={"user": user})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ==========================================
# STARTUP & INDEX INITIALIZATION
# ==========================================

@app.on_event("startup")
async def init_indexes():
    """Ensure database indexes exist for performance and strict user isolation."""
    try:
        await users_collection.create_index("email", unique=True)
        await user_profiles_collection.create_index("user_id", unique=True)
        await credit_evaluations_collection.create_index([("user_id", 1), ("created_at", -1)])
        await credit_score_history_collection.create_index([("user_id", 1), ("created_at", -1)])
        await user_activity_collection.create_index([("user_id", 1), ("created_at", -1)])
        await otps_collection.create_index([("email", 1), ("purpose", 1)])
    except Exception as e:
        print(f"Notice during index creation: {e}")


# ==========================================
# AUTH & USER HELPERS
# ==========================================

async def get_current_user_optional(request: Request):
    """Extract user from Authorization header or cookie. Returns None if not authenticated."""
    token = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("creditpulse_token")
    if not token or token in ("undefined", "null", ""):
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    email = payload.get("sub")
    if not email:
        return None
    user = await users_collection.find_one({"email": email.lower().strip()})
    if user:
        user["_id"] = str(user["_id"])
    return user


async def require_auth(request: Request):
    """Require authentication. Raises 401 if not authenticated."""
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def build_user_id_filter(user_id: str) -> dict:
    """Ensure consistent user_id querying across string and ObjectId representations."""
    uid_str = str(user_id)
    candidates = [uid_str]
    try:
        candidates.append(ObjectId(uid_str))
    except Exception:
        pass
    return {"user_id": {"$in": candidates}}


async def log_user_activity(user_id: str, action: str, details: dict = None):
    """Append a user-scoped activity event."""
    try:
        activity_doc = {
            "user_id": str(user_id),
            "action": action,
            "type": action,
            "details": details or {},
            "created_at": datetime.now(timezone.utc)
        }
        await user_activity_collection.insert_one(activity_doc)
    except Exception as e:
        print(f"Activity logging notice: {e}")


async def ensure_user_profile(user: dict):
    """Ensure user profile exists in user_profiles collection."""
    user_id_str = str(user["_id"])
    profile = await user_profiles_collection.find_one({"user_id": user_id_str})
    if not profile:
        profile = {
            "user_id": user_id_str,
            "full_name": user.get("full_name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone"),
            "created_at": user.get("created_at", datetime.now(timezone.utc)),
            "updated_at": datetime.now(timezone.utc)
        }
        await user_profiles_collection.insert_one(profile)
    return profile


# ==========================================
# PAGE ROUTES (USER-SCOPED)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request, 
        name="home.html",
        context={"user": user}
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/authenticate?intent=dashboard", status_code=303)

    user_id_str = str(user["_id"])
    user_filter = build_user_id_filter(user_id_str)

    # Query ONLY current user's evaluations
    cursor = credit_evaluations_collection.find(user_filter).sort("created_at", -1)
    raw_evals = await cursor.to_list(length=100)

    # Legacy fallback check (in case user had records in application_collection with their user_id or email)
    if not raw_evals:
        cursor_legacy = application_collection.find({
            "$or": [{"user_id": user_id_str}, {"user_email": user["email"]}]
        }).sort("created_at", -1)
        raw_evals = await cursor_legacy.to_list(length=100)

    evaluations = []
    approved_count = 0
    rejected_count = 0
    now = datetime.now(timezone.utc)
    this_month_count = 0

    for doc in raw_evals:
        doc["_id"] = str(doc["_id"])
        created_at = doc.get("created_at")
        if created_at:
            if hasattr(created_at, "year") and created_at.year == now.year and created_at.month == now.month:
                this_month_count += 1
            if hasattr(created_at, "strftime"):
                doc["formatted_date"] = created_at.strftime("%b %d, %Y • %I:%M %p")
            else:
                doc["formatted_date"] = str(created_at)
        else:
            doc["formatted_date"] = "N/A"

        app_data = doc.get("applicant_data") or doc.get("application_data") or {}
        doc["applicant_data"] = app_data
        doc["application_data"] = app_data
        pred_data = doc.get("prediction") or doc.get("result") or {}
        doc["prediction"] = pred_data
        doc["result"] = pred_data

        pred_status = pred_data.get("status", "")
        if pred_status == "Approved":
            approved_count += 1
        elif pred_status == "Rejected":
            rejected_count += 1

        evaluations.append(doc)

    # Latest credit score for current user
    latest_score_doc = await credit_score_history_collection.find_one(
        user_filter,
        sort=[("created_at", -1)]
    )

    # Score trend for current user (chronological)
    score_cursor = credit_score_history_collection.find(user_filter).sort("created_at", 1)
    score_history = await score_cursor.to_list(length=50)
    score_trend = []
    for s in score_history:
        created_at = s.get("created_at")
        date_str = created_at.strftime("%b %d") if hasattr(created_at, "strftime") else "Date"
        score_trend.append({
            "date": date_str,
            "score": s.get("predicted_score", 0),
            "risk_band": s.get("risk_band", "")
        })

    # Recent user activity (strictly current user)
    act_cursor = user_activity_collection.find(user_filter).sort("created_at", -1).limit(8)
    raw_activities = await act_cursor.to_list(length=8)
    activities = []
    for act in raw_activities:
        created_at = act.get("created_at")
        time_str = created_at.strftime("%b %d, %I:%M %p") if hasattr(created_at, "strftime") else ""
        activities.append({
            "action": (act.get("action") or act.get("type") or "").replace("_", " ").title(),
            "details": act.get("details", {}),
            "time": time_str
        })

    summary = {
        "total_evaluations": len(evaluations),
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "this_month_count": this_month_count,
        "latest_evaluation": evaluations[0] if evaluations else None,
        "latest_score": latest_score_doc.get("predicted_score") if latest_score_doc else None,
        "latest_score_band": latest_score_doc.get("risk_band") if latest_score_doc else None,
        "latest_score_color": latest_score_doc.get("rating_color") if latest_score_doc else None,
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "summary": summary,
            "evaluations": evaluations[:10],
            "all_evaluations_count": len(evaluations),
            "score_trend": score_trend,
            "activities": activities
        }
    )


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/authenticate?intent=analytics", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={"user": user}
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/authenticate?intent=history", status_code=303)

    user_id_str = str(user["_id"])
    evaluations = []
    history_error = None

    try:
        user_filter = build_user_id_filter(user_id_str)
        cursor = credit_evaluations_collection.find(user_filter).sort("created_at", -1)
        raw_evals = await cursor.to_list(length=100)

        # Legacy fallback if no modern evals exist
        if not raw_evals:
            cursor_legacy = application_collection.find({
                "$or": [{"user_id": user_id_str}, {"user_email": user["email"]}]
            }).sort("created_at", -1)
            raw_evals = await cursor_legacy.to_list(length=100)

        for doc in raw_evals:
            doc["_id"] = str(doc["_id"])
            created_at = doc.get("created_at")
            if created_at and hasattr(created_at, "strftime"):
                doc["formatted_date"] = created_at.strftime("%b %d, %Y • %I:%M %p")
            else:
                doc["formatted_date"] = str(created_at) if created_at else "N/A"

            app_data = doc.get("applicant_data") or doc.get("application_data") or {}
            doc["applicant_data"] = app_data
            doc["application_data"] = app_data
            pred_data = doc.get("prediction") or doc.get("result") or {}
            doc["prediction"] = pred_data
            doc["result"] = pred_data
            doc["evaluation_type"] = "Credit & Loan Evaluation"
            evaluations.append(doc)
    except Exception as e:
        print(f"Error loading evaluation history: {e}")
        history_error = "Unable to load your history. Please try again."

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"user": user, "evaluations": evaluations, "history_error": history_error}
    )


@app.get("/credit-score", response_class=HTMLResponse)
async def credit_score_page(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="credit_score.html",
        context={"user": user}
    )


@app.get("/application", response_class=HTMLResponse)
async def application_form(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user}
    )


@app.get("/authenticate", response_class=HTMLResponse)
async def auth_page(request: Request):
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="authenticate.html"
    )


@app.get("/result", response_class=HTMLResponse)
async def view_result(request: Request, status: str = "Rejected", prob: float = 0.0):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"status": status, "probability": prob, "user": user},
    )


@app.get("/record/{record_id}", response_class=HTMLResponse)
async def view_single_record(request: Request, record_id: str):
    """View details of a single evaluation. Strictly verifies ownership by the authenticated user."""
    user = await require_auth(request)
    
    try:
        obj_id = ObjectId(record_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Record ID")

    # Find record in credit_evaluations or legacy application_collection
    record = await credit_evaluations_collection.find_one({"_id": obj_id})
    if not record:
        record = await application_collection.find_one({"_id": obj_id})
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # STRICT USER ISOLATION CHECK
    rec_user_id = str(record.get("user_id", ""))
    current_user_id = str(user["_id"])
    rec_email = record.get("user_email") or record.get("applicant_data", {}).get("Email")

    if rec_user_id:
        if rec_user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only view your own records.")
    elif rec_email and rec_email.lower().strip() != user["email"].lower().strip():
        raise HTTPException(status_code=403, detail="Access denied. You can only view your own records.")

    # Format dates
    if "created_at" in record and hasattr(record["created_at"], "strftime"):
        record["formatted_date"] = record["created_at"].strftime("%B %d, %Y • %I:%M:%S %p UTC")
    record["_id"] = str(record["_id"])

    return templates.TemplateResponse(
        request=request,
        name="record_detail.html",
        context={"record": record, "user": user}
    )


@app.get("/help-center", response_class=HTMLResponse)
async def help_center(request: Request):
    user = await get_current_user_optional(request)
    return templates.TemplateResponse(
        request=request, 
        name="help_center.html",
        context={"user": user}
    )


@app.get("/credit-dashboard", response_class=HTMLResponse)
async def credit_dashboard_page(request: Request):
    user = await get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/authenticate?intent=credit-dashboard", status_code=303)
    
    user_email = (user.get("email") or "").lower().strip()
    user_id_str = str(user.get("_id", ""))

    # Find profile by user_id or user_email
    profile = await credit_profiles_collection.find_one({
        "$or": [
            {"user_id": user_id_str},
            {"user_email": user_email}
        ]
    })
    
    credit_data = None
    if profile:
        credit_limit = float(profile.get("credit_limit") or 0.0)
        used_credit = float(profile.get("used_credit") or 0.0)
        available = credit_limit - used_credit
        utilization = (used_credit / credit_limit * 100.0) if credit_limit > 0 else 0.0
        
        raw_txns = profile.get("transactions") or []
        formatted_txns = []
        for t in raw_txns[-10:]:
            d = t.get("date")
            date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d or "")[:10]
            formatted_txns.append({
                "amount": float(t.get("amount") or 0.0),
                "description": str(t.get("description") or "Transaction"),
                "category": str(t.get("category") or "General"),
                "date": date_str
            })

        credit_data = {
            "credit_limit": credit_limit,
            "used_credit": used_credit,
            "available_credit": round(available, 2),
            "utilization": round(utilization, 1),
            "transactions": formatted_txns,
            "suggestions": get_what_can_i_buy(available)
        }
    
    return templates.TemplateResponse(
        request=request,
        name="credit_dashboard.html",
        context={"user": user, "credit_data": credit_data}
    )


# ==========================================
# CALCULATION & ML APIS (USER-SCOPED)
# ==========================================

@app.post("/api/predict")
async def predict_loan(application: LoanApplicationInput, request: Request):
    """
    Evaluate loan eligibility.
    STRICT REQUIREMENT: Only authenticated users can perform evaluations.
    Saves calculation snapshot, result, authenticated user_id, and logs activity.
    """
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required before running evaluation")

    data = application.model_dump()
    status, prob = await asyncio.to_thread(get_loan_prediction, data)

    user_id_str = str(user["_id"])
    now_dt = datetime.now(timezone.utc)

    record = {
        "user_id": user_id_str,
        "user_email": user["email"],
        "applicant_data": data,
        "application_data": data,
        "prediction": {
            "status": status,
            "probability": prob,
        },
        "result": {
            "status": status,
            "probability": prob,
        },
        "created_at": now_dt,
    }

    # Save to user-scoped credit_evaluations
    try:
        insert_res = await credit_evaluations_collection.insert_one(record)
        if not insert_res.acknowledged or not insert_res.inserted_id:
            raise RuntimeError("Database write not acknowledged by MongoDB.")
        eval_id = str(insert_res.inserted_id)
    except Exception as db_err:
        print(f"CRITICAL: Failed to save evaluation to MongoDB: {db_err}")
        raise HTTPException(
            status_code=500,
            detail="Evaluation calculated, but saving to your history database failed. Record was not saved."
        )

    # Also save with user_id into legacy application_collection for backward compatibility
    try:
        await application_collection.insert_one({**record, "_id": insert_res.inserted_id})
    except Exception:
        pass

    # Log user activity
    await log_user_activity(user_id_str, "CREDIT_EVALUATION_COMPLETED", {
        "evaluation_id": eval_id,
        "status": status,
        "probability": round(prob, 4),
        "loan_amount": data.get("Loan_Amount")
    })

    return {
        "status": status,
        "probability": prob,
        "evaluation_id": eval_id,
        "saved": True,
        "message": "✓ Evaluation completed and saved to your history."
    }


@app.post("/api/credit-score")
async def calculate_credit_score_endpoint(payload: CreditScoreInput, request: Request):
    """
    Calculate educational CreditPulse credit-score estimate (300-900).
    STRICT REQUIREMENT: Only authenticated users can calculate score.
    Saves snapshot, breakdown, authenticated user_id, and logs activity.
    """
    user = await get_current_user_optional(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required before checking credit score")

    data_dict = payload.model_dump()
    score_result = calculate_credit_score_estimate(data_dict)

    user_id_str = str(user["_id"])
    now_dt = datetime.now(timezone.utc)

    score_doc = {
        "user_id": user_id_str,
        "user_email": user["email"],
        "inputs": data_dict,
        "predicted_score": score_result["estimated_score"],
        "risk_band": score_result["risk_band"],
        "rating_color": score_result["rating_color"],
        "factors": score_result["factors"],
        "what_helped": score_result["what_helped"],
        "what_reduced": score_result["what_reduced"],
        "how_to_improve": score_result["how_to_improve"],
        "created_at": now_dt
    }

    res = await credit_score_history_collection.insert_one(score_doc)
    score_id = str(res.inserted_id)

    # Log user activity
    await log_user_activity(user_id_str, "CREDIT_SCORE_CHECKED", {
        "score_id": score_id,
        "score": score_result["estimated_score"],
        "risk_band": score_result["risk_band"]
    })

    return {
        **score_result,
        "score": score_result["estimated_score"],
        "rating": score_result["risk_band"],
        "status": "Success",
        "_id": score_id
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_advisor(payload: ChatRequest):
    reply = generate_loan_advice(
        user_message=payload.user_message,
        applicant_data=payload.applicant_data,
        status=payload.status,
        probability=payload.probability
    )
    return ChatResponse(reply=reply)


# ==========================================
# USER-SCOPED ANALYTICS & DATA APIS
# ==========================================

@app.get("/api/user/dashboard-data")
async def get_user_dashboard_data(request: Request):
    """Returns dynamic stats and recent entries for CURRENT authenticated user only."""
    user = await require_auth(request)
    user_id_str = str(user["_id"])
    user_filter = build_user_id_filter(user_id_str)

    cursor = credit_evaluations_collection.find(user_filter).sort("created_at", -1)
    raw_evals = await cursor.to_list(length=100)

    if not raw_evals:
        cursor_legacy = application_collection.find({
            "$or": [{"user_id": user_id_str}, {"user_email": user["email"]}]
        }).sort("created_at", -1)
        raw_evals = await cursor_legacy.to_list(length=100)

    now = datetime.now(timezone.utc)
    this_month_count = 0
    approved = 0
    rejected = 0

    evals_list = []
    for doc in raw_evals:
        doc["_id"] = str(doc["_id"])
        created_at = doc.get("created_at")
        if created_at:
            if hasattr(created_at, "year") and created_at.year == now.year and created_at.month == now.month:
                this_month_count += 1
            doc["created_at_iso"] = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
        
        pred = doc.get("prediction") or doc.get("result") or {}
        st = pred.get("status")
        if st == "Approved":
            approved += 1
        elif st == "Rejected":
            rejected += 1
        evals_list.append(doc)

    latest_score_doc = await credit_score_history_collection.find_one(
        user_filter,
        sort=[("created_at", -1)]
    )

    act_cursor = user_activity_collection.find(user_filter).sort("created_at", -1).limit(10)
    raw_acts = await act_cursor.to_list(length=10)
    activities = []
    for act in raw_acts:
        created_at = act.get("created_at")
        activities.append({
            "action": act.get("action", "") or act.get("type", ""),
            "details": act.get("details", {}),
            "time": created_at.strftime("%b %d, %I:%M %p") if hasattr(created_at, "strftime") else ""
        })

    return {
        "user": {"full_name": user.get("full_name"), "email": user.get("email")},
        "total_evaluations": len(evals_list),
        "approved_count": approved,
        "rejected_count": rejected,
        "this_month_count": this_month_count,
        "latest_score": latest_score_doc.get("predicted_score") if latest_score_doc else None,
        "latest_score_band": latest_score_doc.get("risk_band") if latest_score_doc else None,
        "latest_evaluation": evals_list[0] if evals_list else None,
        "recent_evaluations": evals_list[:5],
        "activities": activities
    }


@app.get("/api/user/analytics-data")
async def get_user_analytics_data(request: Request, period: str = Query("30d")):
    """
    Returns aggregated real analytics for CURRENT authenticated user only.
    Filters: 7d, 30d, 3m, 6m, 1y, all.
    """
    user = await require_auth(request)
    user_id_str = str(user["_id"])
    now = datetime.now(timezone.utc)

    # Determine cutoff date
    cutoff = None
    if period == "7d":
        cutoff = now - timedelta(days=7)
    elif period == "30d":
        cutoff = now - timedelta(days=30)
    elif period == "3m":
        cutoff = now - timedelta(days=90)
    elif period == "6m":
        cutoff = now - timedelta(days=180)
    elif period == "1y":
        cutoff = now - timedelta(days=365)

    user_filter = build_user_id_filter(user_id_str)
    date_query = dict(user_filter)
    if cutoff:
        date_query["created_at"] = {"$gte": cutoff}

    cursor = credit_evaluations_collection.find(date_query).sort("created_at", 1)
    evals = await cursor.to_list(length=500)

    score_cursor = credit_score_history_collection.find(date_query).sort("created_at", 1)
    scores = await score_cursor.to_list(length=100)

    # Aggregations
    total_evals = len(evals)
    approved = sum(1 for e in evals if (e.get("prediction") or e.get("result") or {}).get("status") == "Approved")
    rejected = total_evals - approved
    approval_rate = round((approved / total_evals * 100), 1) if total_evals > 0 else 0.0

    # Decision trend by day/month
    timeline = {}
    total_requested_loan = 0
    loan_amounts = []
    dti_values = []
    credit_scores_input = []

    for e in evals:
        ca = e.get("created_at")
        if not ca:
            continue
        day_key = ca.strftime("%b %d") if hasattr(ca, "strftime") else "Date"
        if day_key not in timeline:
            timeline[day_key] = {"date": day_key, "approved": 0, "rejected": 0, "total": 0}
        
        pred = e.get("prediction") or e.get("result") or {}
        st = pred.get("status")
        if st == "Approved":
            timeline[day_key]["approved"] += 1
        elif st == "Rejected":
            timeline[day_key]["rejected"] += 1
        timeline[day_key]["total"] += 1

        inp = e.get("applicant_data") or e.get("application_data") or {}
        amt = float(inp.get("Loan_Amount") or 0)
        if amt > 0:
            total_requested_loan += amt
            loan_amounts.append(amt)
        dti = float(inp.get("DTI_Ratio") or 0)
        if dti > 0:
            dti_values.append(dti)
        cs = float(inp.get("Credit_Score") or 0)
        if cs > 0:
            credit_scores_input.append(cs)

    score_timeline = []
    for s in scores:
        ca = s.get("created_at")
        date_str = ca.strftime("%b %d") if hasattr(ca, "strftime") else "Date"
        score_timeline.append({
            "date": date_str,
            "score": s.get("predicted_score", 0),
            "risk_band": s.get("risk_band", "")
        })

    return {
        "summary": {
            "total_evaluations": total_evals,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": approval_rate,
            "total_requested_loan": total_requested_loan,
            "avg_loan_amount": round(sum(loan_amounts) / len(loan_amounts), 2) if loan_amounts else 0.0,
            "avg_dti": round(sum(dti_values) / len(dti_values), 1) if dti_values else 0.0,
            "avg_input_credit_score": round(sum(credit_scores_input) / len(credit_scores_input), 0) if credit_scores_input else 0,
        },
        "evaluation_timeline": list(timeline.values()),
        "score_timeline": score_timeline,
        "has_data": len(evals) > 0 or len(scores) > 0
    }


@app.get("/api/user/history")
async def get_user_history(request: Request, page: int = 1, limit: int = 10):
    """Paginated evaluation history for current user only."""
    user = await require_auth(request)
    user_id_str = str(user["_id"])
    skip = max(0, (page - 1) * limit)

    try:
        user_filter = build_user_id_filter(user_id_str)
        total_count = await credit_evaluations_collection.count_documents(user_filter)
        cursor = credit_evaluations_collection.find(user_filter).sort("created_at", -1).skip(skip).limit(limit)
        records = await cursor.to_list(length=limit)

        if not records and page == 1:
            legacy_query = {
                "$or": [
                    {"user_id": user_id_str},
                    {"user_email": user["email"]}
                ]
            }
            total_count = await application_collection.count_documents(legacy_query)
            cursor_legacy = application_collection.find(legacy_query).sort("created_at", -1).skip(skip).limit(limit)
            records = await cursor_legacy.to_list(length=limit)

        items = []
        for r in records:
            rec_id = str(r["_id"])
            r["_id"] = rec_id
            r["record_id"] = rec_id
            created_at = r.get("created_at")
            r["formatted_date"] = created_at.strftime("%b %d, %Y • %I:%M %p") if hasattr(created_at, "strftime") else str(created_at)
            app_data = r.get("applicant_data") or r.get("application_data") or {}
            r["applicant_data"] = app_data
            r["application_data"] = app_data
            pred = r.get("prediction") or r.get("result") or {}
            r["prediction"] = pred
            r["result"] = pred
            r["status"] = pred.get("status", "Evaluated")
            r["probability"] = pred.get("probability", 0.0)
            r["evaluation_type"] = "Credit & Loan Evaluation"
            items.append(r)

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit if limit > 0 else 1,
            "records": items,
            "evaluations": items
        }
    except Exception as e:
        print(f"Error fetching user history: {e}")
        raise HTTPException(status_code=500, detail="Unable to load your history. Please try again.")


@app.get("/api/user/activity")
async def get_user_activity(request: Request):
    """Activity log for current authenticated user."""
    user = await require_auth(request)
    user_id_str = str(user["_id"])
    user_filter = build_user_id_filter(user_id_str)

    cursor = user_activity_collection.find(user_filter).sort("created_at", -1).limit(20)
    raw = await cursor.to_list(length=20)
    activities = []
    for r in raw:
        r["_id"] = str(r["_id"])
        created_at = r.get("created_at")
        r["formatted_date"] = created_at.strftime("%b %d, %Y • %I:%M %p") if hasattr(created_at, "strftime") else ""
        r["action"] = r.get("action") or r.get("type") or ""
        activities.append(r)

    return {"activities": activities}


# ==========================================
# AUTH API ENDPOINTS
# ==========================================

@app.post("/api/send-otp")
async def send_otp(request: OTPRequest, purpose: str = "signup"):
    """Send OTP for signup or password reset with rate limiting."""
    email = request.email.lower().strip()
    purpose = purpose.lower().strip()
    if purpose not in ("signup", "reset"):
        raise HTTPException(status_code=400, detail="Invalid OTP purpose")

    def _to_naive_utc(dt) -> datetime:
        if dt is None:
            return None
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    last_otp = await otps_collection.find_one(
        {"email": email, "purpose": purpose},
        sort=[("created_at", -1)]
    )
    if last_otp and last_otp.get("created_at"):
        last_created = _to_naive_utc(last_otp["created_at"])
        now_naive = datetime.utcnow()
        elapsed = (now_naive - last_created).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            remaining = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(
                status_code=429, 
                detail=f"Please wait {remaining} seconds before requesting another OTP"
            )

    user_name = ""
    if purpose == "reset":
        user = await users_collection.find_one({"email": email})
        if not user:
            return {"message": "If this email is registered, you will receive an OTP shortly."}
        user_name = user.get("full_name", "")
    
    if purpose == "signup":
        existing = await users_collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="This email is already registered. Please sign in.")

    otp = generate_otp()
    otp_hashed = hash_otp(otp)

    now_utc = datetime.utcnow()
    otp_record = {
        "email": email,
        "otp_hash": otp_hashed,
        "purpose": purpose,
        "attempts": 0,
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(minutes=OTP_EXPIRY_MINUTES)
    }

    await otps_collection.delete_many({"email": email, "purpose": purpose})
    await otps_collection.insert_one(otp_record)

    try:
        send_otp_email(email, otp, purpose, user_name)
        return {"message": "OTP sent successfully"}
    except EmailConfigurationError as e:
        await otps_collection.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(status_code=500, detail=str(e))
    except EmailDeliveryError as e:
        await otps_collection.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        await otps_collection.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(status_code=500, detail="Failed to send OTP email. Please try again.")


@app.post("/api/verify-signup")
async def verify_and_signup(data: VerifySignup):
    """Verify OTP and create account."""
    email = data.email.lower().strip()
    existing_user = await users_collection.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered. Please sign in.")

    otp_record = await otps_collection.find_one(
        {"email": email, "purpose": "signup"},
        sort=[("created_at", -1)]
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No verification code found. Please request an OTP.")

    expires_at = otp_record.get("expires_at")
    if expires_at:
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            expires_at_naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expires_at_naive = expires_at
        if datetime.utcnow() > expires_at_naive:
            await otps_collection.delete_many({"email": email, "purpose": "signup"})
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    attempts = otp_record.get("attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        await otps_collection.delete_many({"email": email, "purpose": "signup"})
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new OTP.")

    if not verify_otp_hash(data.otp.strip(), otp_record.get("otp_hash", "")):
        await otps_collection.update_one(
            {"_id": otp_record["_id"]},
            {"$inc": {"attempts": 1}}
        )
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        if remaining <= 0:
            await otps_collection.delete_many({"email": email, "purpose": "signup"})
            raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new OTP.")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid OTP. {remaining} attempt(s) remaining."
        )

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        hashed_pwd = get_password_hash(data.password)
        now_dt = datetime.now(timezone.utc)
        user_dict = {
            "full_name": data.full_name.strip(),
            "email": email,
            "phone": data.phone.strip() if data.phone else None,
            "password": hashed_pwd,
            "email_verified": True,
            "created_at": now_dt
        }
        res = await users_collection.insert_one(user_dict)
        user_dict["_id"] = str(res.inserted_id)

        # Create linked user profile & log account creation
        await ensure_user_profile(user_dict)
        await log_user_activity(user_dict["_id"], "ACCOUNT_CREATED", {"email": email})

        # Clean up OTPs
        await otps_collection.delete_many({"email": email, "purpose": "signup"})

        token = create_access_token(data={"sub": email})
        return {"message": "Account created successfully!", "access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred during account creation. Please try again.")


@app.post("/api/login")
async def login(data: UserLogin):
    """Login with user activity logging and rate-limiting."""
    email = data.email.lower().strip()
    user = await users_collection.find_one({"email": email})
    
    if not user or not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    user_id_str = str(user["_id"])

    # If Two-Factor Authentication is enabled, issue OTP challenge instead of direct token
    if user.get("two_factor_enabled", False):
        otp = generate_otp()
        otp_hashed = hash_otp(otp)
        now_utc = datetime.utcnow()
        await otps_collection.delete_many({"email": email, "purpose": "2fa_login"})
        await otps_collection.insert_one({
            "email": email,
            "otp_hash": otp_hashed,
            "purpose": "2fa_login",
            "attempts": 0,
            "created_at": now_utc,
            "expires_at": now_utc + timedelta(minutes=5)
        })
        try:
            await send_otp_email(
                recipient_email=email,
                recipient_name=user.get("full_name", "User"),
                otp=otp,
                purpose="2fa_login"
            )
        except Exception as e:
            print(f"Notice: OTP email send notice: {e}")

        return {
            "requires_2fa": True,
            "email": email,
            "message": "Two-Factor Authentication is enabled. Please enter the verification code sent to your email."
        }

    token = create_access_token(data={"sub": user["email"]})

    # Ensure profile and log login activity
    await ensure_user_profile(user)
    await log_user_activity(user_id_str, "LOGIN", {"email": user["email"]})

    return {
        "access_token": token, 
        "token_type": "bearer",
        "user": {
            "full_name": user.get("full_name", ""),
            "email": user["email"]
        }
    }


@app.post("/api/login/2fa-verify")
async def login_2fa_verify(data: TwoFactorLoginVerify):
    """Complete login when 2FA is enabled."""
    email = data.email.lower().strip()
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")

    otp_record = await otps_collection.find_one(
        {"email": email, "purpose": "2fa_login"},
        sort=[("created_at", -1)]
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="No 2FA verification code found. Please sign in again.")

    expires_at = otp_record.get("expires_at")
    if expires_at:
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            expires_at_naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expires_at_naive = expires_at
        if datetime.utcnow() > expires_at_naive:
            await otps_collection.delete_many({"email": email, "purpose": "2fa_login"})
            raise HTTPException(status_code=400, detail="Verification code expired. Please sign in again.")

    if not verify_otp_hash(data.otp.strip(), otp_record.get("otp_hash", "")):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    await otps_collection.delete_many({"email": email, "purpose": "2fa_login"})

    user_id_str = str(user["_id"])
    token = create_access_token(data={"sub": user["email"]})
    await ensure_user_profile(user)
    await log_user_activity(user_id_str, "LOGIN_2FA", {"email": user["email"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "full_name": user.get("full_name", ""),
            "email": user["email"]
        }
    }


@app.post("/api/reset-password")
async def reset_password(data: ResetPassword):
    """Verify OTP and reset password."""
    email = data.email.lower().strip()
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request")

    otp_record = await otps_collection.find_one(
        {"email": email, "purpose": "reset"},
        sort=[("created_at", -1)]
    )

    if not otp_record:
        raise HTTPException(status_code=400, detail="No reset code found. Please request a new one.")

    expires_at = otp_record.get("expires_at")
    if expires_at:
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            expires_at_naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expires_at_naive = expires_at
        if datetime.utcnow() > expires_at_naive:
            await otps_collection.delete_many({"email": email, "purpose": "reset"})
            raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    attempts = otp_record.get("attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        await otps_collection.delete_many({"email": email, "purpose": "reset"})
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new OTP.")

    if not verify_otp_hash(data.otp.strip(), otp_record.get("otp_hash", "")):
        await otps_collection.update_one(
            {"_id": otp_record["_id"]},
            {"$inc": {"attempts": 1}}
        )
        remaining = OTP_MAX_ATTEMPTS - (attempts + 1)
        if remaining <= 0:
            await otps_collection.delete_many({"email": email, "purpose": "reset"})
            raise HTTPException(status_code=429, detail="Too many failed attempts. Please request a new OTP.")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid OTP. {remaining} attempt(s) remaining."
        )

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        hashed_pwd = get_password_hash(data.new_password)
        await users_collection.update_one(
            {"email": email},
            {"$set": {"password": hashed_pwd}}
        )
        await otps_collection.delete_many({"email": email, "purpose": "reset"})
        await log_user_activity(str(user["_id"]), "PASSWORD_CHANGED")
        
        return {"message": "Password updated successfully!"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred during password reset. Please try again.")


@app.post("/api/change-password")
async def change_password(data: ChangePassword, request: Request):
    """Change the authenticated user's password."""
    user = await require_auth(request)
    
    if not verify_password(data.current_password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    hashed_pwd = get_password_hash(data.new_password)
    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {"password": hashed_pwd}}
    )
    await log_user_activity(str(user["_id"]), "PASSWORD_CHANGED")
    return {"message": "Password updated successfully"}


@app.post("/api/logout")
async def logout(request: Request):
    """Log out current user, clear session cookie, and log activity."""
    user = await get_current_user_optional(request)
    if user:
        await log_user_activity(str(user["_id"]), "LOGOUT", {"email": user.get("email")})
    
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="creditpulse_token", path="/")
    return response


# ==========================================
# TWO-FACTOR AUTHENTICATION APIS
# ==========================================

@app.get("/api/2fa/status")
async def get_2fa_status(request: Request):
    """Get current 2FA status for the authenticated user."""
    user = await require_auth(request)
    return {
        "enabled": bool(user.get("two_factor_enabled", False)),
        "email": user["email"]
    }


@app.post("/api/2fa/request-enable")
async def request_enable_2fa(request: Request):
    """Generate and email OTP to enable 2FA."""
    user = await require_auth(request)
    email = user["email"]

    otp = generate_otp()
    otp_hashed = hash_otp(otp)
    now_utc = datetime.utcnow()

    await otps_collection.delete_many({"email": email, "purpose": "2fa_enable"})
    await otps_collection.insert_one({
        "email": email,
        "otp_hash": otp_hashed,
        "purpose": "2fa_enable",
        "attempts": 0,
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(minutes=10)
    })

    try:
        await send_otp_email(
            recipient_email=email,
            recipient_name=user.get("full_name", "User"),
            otp=otp,
            purpose="2fa_enable"
        )
    except Exception as e:
        print(f"Notice: OTP email notice: {e}")

    return {"message": f"Verification code sent to {email}"}


@app.post("/api/2fa/confirm-enable")
async def confirm_enable_2fa(data: TwoFactorConfirm, request: Request):
    """Verify OTP and enable 2FA for the authenticated user."""
    user = await require_auth(request)
    email = user["email"]

    otp_record = await otps_collection.find_one(
        {"email": email, "purpose": "2fa_enable"},
        sort=[("created_at", -1)]
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="No pending 2FA setup request found. Please request a new code.")

    expires_at = otp_record.get("expires_at")
    if expires_at:
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            expires_at_naive = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            expires_at_naive = expires_at
        if datetime.utcnow() > expires_at_naive:
            await otps_collection.delete_many({"email": email, "purpose": "2fa_enable"})
            raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    if not verify_otp_hash(data.otp.strip(), otp_record.get("otp_hash", "")):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    await users_collection.update_one(
        {"email": email},
        {"$set": {"two_factor_enabled": True}}
    )
    await otps_collection.delete_many({"email": email, "purpose": "2fa_enable"})
    await log_user_activity(str(user["_id"]), "2FA_ENABLED")

    return {"message": "Two-Factor Authentication successfully enabled.", "enabled": True}


@app.post("/api/2fa/disable")
async def disable_2fa(data: TwoFactorDisable, request: Request):
    """Disable 2FA after verifying the user's password."""
    user = await require_auth(request)
    if not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Incorrect password. Cannot disable Two-Factor Authentication.")

    await users_collection.update_one(
        {"email": user["email"]},
        {"$set": {"two_factor_enabled": False}}
    )
    await log_user_activity(str(user["_id"]), "2FA_DISABLED")

    return {"message": "Two-Factor Authentication has been disabled.", "enabled": False}


# ==========================================
# USER PROFILE API
# ==========================================

@app.get("/api/me")
async def get_me(request: Request):
    """Get current authenticated user and profile."""
    user = await require_auth(request)
    profile = await ensure_user_profile(user)
    if profile and "_id" in profile:
        profile["_id"] = str(profile["_id"])
    if profile and "created_at" in profile and hasattr(profile["created_at"], "isoformat"):
        profile["created_at"] = profile["created_at"].isoformat()
    if profile and "updated_at" in profile and hasattr(profile["updated_at"], "isoformat"):
        profile["updated_at"] = profile["updated_at"].isoformat()

    return {
        "user_id": str(user["_id"]),
        "full_name": user.get("full_name", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone"),
        "created_at": str(user.get("created_at", "")),
        "profile": profile
    }


# ==========================================
# CREDIT PROFILE & SIMULATOR APIS
# ==========================================

@app.post("/api/credit-profile")
async def create_or_update_credit_profile(data: CreditProfileCreate, request: Request):
    user = await require_auth(request)
    existing = await credit_profiles_collection.find_one({"user_email": user["email"]})
    
    if existing:
        await credit_profiles_collection.update_one(
            {"user_email": user["email"]},
            {"$set": {"credit_limit": data.credit_limit, "updated_at": datetime.now(timezone.utc)}}
        )
    else:
        profile = {
            "user_email": user["email"],
            "credit_limit": data.credit_limit,
            "used_credit": 0,
            "transactions": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await credit_profiles_collection.insert_one(profile)
    
    return {"message": "Credit profile updated successfully"}


@app.get("/api/credit-profile")
async def get_credit_profile(request: Request):
    user = await require_auth(request)
    profile = await credit_profiles_collection.find_one({"user_email": user["email"]})
    if not profile:
        return {"credit_limit": 0, "used_credit": 0, "available_credit": 0, "utilization": 0, "transactions": []}
    
    credit_limit = profile.get("credit_limit", 0)
    used_credit = profile.get("used_credit", 0)
    available = credit_limit - used_credit
    utilization = (used_credit / credit_limit * 100) if credit_limit > 0 else 0
    
    return {
        "credit_limit": credit_limit,
        "used_credit": used_credit,
        "available_credit": round(available, 2),
        "utilization": round(utilization, 1),
        "transactions": profile.get("transactions", [])[-20:],
        "suggestions": get_what_can_i_buy(available)
    }


@app.post("/api/credit-transaction")
async def add_credit_transaction(data: CreditTransaction, request: Request):
    user = await require_auth(request)
    profile = await credit_profiles_collection.find_one({"user_email": user["email"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Credit profile not found. Please set up your credit limit first.")
    
    available = profile["credit_limit"] - profile["used_credit"]
    if data.amount > available:
        raise HTTPException(status_code=400, detail="Transaction exceeds your available credit")
    
    transaction = {
        "amount": data.amount,
        "description": data.description,
        "category": data.category,
        "date": datetime.now(timezone.utc).isoformat()
    }
    
    await credit_profiles_collection.update_one(
        {"user_email": user["email"]},
        {
            "$inc": {"used_credit": data.amount},
            "$push": {"transactions": transaction},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    return {"message": "Transaction recorded", "transaction": transaction}


@app.post("/api/simulate-purchase")
async def simulate_purchase_endpoint(data: PurchaseSimulation, request: Request):
    user = await require_auth(request)
    profile = await credit_profiles_collection.find_one({"user_email": user["email"]})
    if not profile:
        raise HTTPException(status_code=404, detail="Credit profile not found")
    
    result = simulate_purchase(
        credit_limit=profile["credit_limit"],
        used_credit=profile["used_credit"],
        purchase_amount=data.amount
    )
    return result


@app.post("/api/save-visitor")
async def vistors(data: VisitorData):
    record = {
        "ip_address": data.ip_address,
        "consent_status": data.consent_status,
        "visited_at": datetime.now(timezone.utc)
    }
    await application_collection.database["visitors"].insert_one(record)
    return {"status": "success", "message": "IP Saved to Database"}
