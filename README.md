# CreditPulse 💳⚡

## Credit Studio

Open `/credit-tools` for the new credit planning workspace, available without signing in:

- **EMI & prepayment:** fixed-rate amortization, extra monthly repayments, interest savings, upfront fees, and downloadable CSV schedules.
- **Loan comparison:** compare two offers for the same principal by payment and total cost.
- **Debt payoff:** avalanche and snowball simulations, fixed minimum payments, automatic payment rollover, and explicit results when a plan exceeds 600 months.
- **Affordability:** calculate borrowing capacity using take-home income, living costs, existing EMIs, savings reserves, and a user-selected DTI ceiling.
- **Card utilization:** combined and per-card usage, available credit, and paydown amounts for a selected target.

Calculations are stateless and not saved. Values are INR; rates are entered by the user. These are educational scenarios, not official bureau scores, live bank offers, or lending decisions. The existing account, score-estimation, analytics, history, and ML evaluation features remain available.

### Local setup

Use Python 3.11 or 3.12 in a fresh virtual environment and install `requirements.txt`. Copy `.env.example` to `.env` and configure MongoDB, a stable random `SECRET_KEY`, and SMTP credentials for registration and password recovery. `GEMINI_API_KEY` is optional; the advisor returns a setup message when it is missing. Never commit credentials.

```powershell
python -m venv loan_env
.\loan_env\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/credit-tools`. API documentation is at `/docs`. The five calculator endpoints are `POST /api/tools/loan`, `/compare`, `/payoff`, `/affordability`, and `/utilization` (all under `/api/tools`). The tools do not require MongoDB, although full application startup attempts to initialize database indexes and account features require a working database.

### Verification

```powershell
pip install httpx
python -m unittest discover -s tests -v
```

The tests cover known EMI values, zero interest, principal conservation, prepayments, validation, comparison fees, affordability limits, over-limit cards, debt rollover, strategy differences, and non-payoff scenarios.

### Scope and deployment notes

- No bureau, bank, payment processor, or credit-report dispute integration is included. Transactions in the existing credit dashboard are internal records.
- Calculator assumptions: fixed annual nominal rates, monthly interest, payments at month end, no new borrowing, and upfront fees outside the loan. Lender rounding, variable rates, penalties, insurance, and taxes may differ.
- Debt minimum payments stay fixed at their entered values; simulations stop after 600 months.
- Existing ML artifacts have not been retrained or independently validated for lending use. Review dataset provenance, leakage, calibration, and protected demographic inputs before considering real underwriting.
- Configure HTTPS, restricted CORS, abuse protection, database backups, and production session controls before a public launch. This feature expansion is not a production security audit.
- SMTP credentials previously embedded in source have been removed; revoke and replace those credentials with environment-configured ones. Without `SECRET_KEY`, the development fallback changes on process restart and differs between workers.

Educational references: [CFPB debt repayment strategies](https://www.consumerfinance.gov/archive/blog/how-reduce-your-debt/) and [credit utilization and repayment habits](https://www.consumerfinance.gov/consumer-tools/credit-reports-and-scores/how-to-rebuild-your-credit/).

**AI-Powered Loan Underwriting & Financial Advisory Platform**

CreditPulse is a modern FinTech web application designed to automate and streamline the loan underwriting process. By combining predictive Machine Learning (XGBoost) with Generative AI (Google Gemini), it not only evaluates loan applications instantly but also provides users with real-time, personalized financial advice.

---

## 🚀 Key Features

*   **Instant Risk Assessment:** Evaluates applicant financial and demographic data to predict loan approval/rejection with a high-accuracy probability score.
*   **CreditPulse AI Advisor:** An integrated chatbot powered by Google Gemini (Gemini 2.5 Flash) that streams responses using your current data.
*   **Context-Aware Analytics:** Click on any past application to view its specific data and ask the AI targeted questions (e.g., *"Why was this loan rejected?"* or *"How can I improve this profile?"*).
*   **Records & Analytics Dashboard:** A comprehensive view for administrators to track historical records, approval vs. rejection ratios, and loan purpose distributions.
*   **Modern UI/UX:** Responsive, clean interface built with HTML5 and Tailwind CSS, featuring floating widgets and Markdown-formatted AI responses.

---

## 🛠️ Tech Stack

**Frontend:**
*   HTML5 & CSS3
*   Tailwind CSS
*   JavaScript
*   Jinja2 Templates


**Backend:**
*   Python 3
*   FastAPI (Asynchronous API framework)

**Database & AI/ML:**
*   MongoDB (NoSQL database for storing application records)
*   XGBoost & Scikit-Learn (Machine learning pipeline and data processing)
*   Google Gemini API (Generative AI integration)

---

## 📂 Project Structure
```text
credit_wise_loan/
│
├── app/
│   ├── main.py               # FastAPI application routing and endpoints
│   ├── services.py           # AI integration (Gemini API) and core logic
│   ├── database.py           # MongoDB connection setup
│   ├── schemas.py            # Pydantic models for data validation
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── index.html        # Application Form
│   │   ├── result.html       # Evaluation Result & AI Chat
│   │   ├── dashboard.html    # Records & Analytics
│   │   ├── record_detail.html# Specific Record Analysis
│   │   └── help_center.html  # Dedicated AI Help Desk
│   └── static/
│       └── js/
│           ├── main.js       # Core JS (Form handling, Typewriter AI Chat)
│           └── dashboard.js  # Dashboard charts logic
│
├── ml_pipeline/              # XGBoost models, scalers, and encoders
├── dataset/                  # Raw and preprocessed CSV data
├── requirements.txt          # Python dependencies
└── README.md
```
## 👨‍💻Author

**Anand Tripathi**  
*Bachelor of Computer Applications (BCA)*

* 💼 **LinkedIn:** https://www.linkedin.com/in/anand-tripathi01/
* 🐙 **GitHub:** https://github.com/anandtripathi0
* 📧 **Email:** tripathianand086@gmail.com
