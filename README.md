# CreditPulse 💳⚡
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

## 👨‍💻 Author

**Anand Tripathi**  
*Bachelor of Computer Applications (BCA)*

* 💼 **LinkedIn:** https://www.linkedin.com/in/anand-tripathi01/
* 🐙 **GitHub:** https://github.com/anandtripathi0
* 📧 **Email:** tripathianand086@gmail.com