import os
import secrets
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI","mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME","credit_db")

# JWT Auth
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Email (credentials are supplied through the environment)
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

# OTP
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
