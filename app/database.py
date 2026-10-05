from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)

db = client[DB_NAME]

# Core Collections
users_collection = db.users
user_profiles_collection = db.user_profiles
credit_evaluations_collection = db.credit_evaluations
credit_score_history_collection = db.credit_score_history
user_activity_collection = db.user_activity
credit_profiles_collection = db.credit_profiles
otps_collection = db.otps

application_collection = db.get_collection("loan_applications")