"""
Configuration module for CV Servant.
Loads environment variables and sets up project paths.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
APPLICATIONS_DIR = DATA_DIR / "applications"
INBOX_IMAGES_DIR = DATA_DIR / "inbox_images"
EXPORTS_DIR = DATA_DIR / "exports"
EXCEL_TRACKER_PATH = DATA_DIR / "Job_Applications_Tracker.xlsx"

# Load .env file
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Gmail Configuration
GMAIL_USER = os.getenv("GMAIL_USER", "arch.mustafa.mahmoud.2007@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
GMAIL_IMAP_SERVER = "imap.gmail.com"
GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465

# Ollama AI Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen3.5:9b")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:8b")

# Telegram Bot (for Remote Mobile Approval)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Google Drive Sync Paths
GDRIVE_INBOX_DIR = os.getenv("GDRIVE_INBOX_DIR", "")
GDRIVE_ARCHIVE_DIR = os.getenv("GDRIVE_ARCHIVE_DIR", "")

# Target Countries & Visa Sponsorship Keywords
TARGET_COUNTRIES = {
    "Australia": {
        "keywords": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide"],
        "sponsorship_indicators": [
            "visa sponsorship", "tss 482", "subclass 482", "subclass 186",
            "pr pathway", "sponsor visa", "relocation assistance", "sponsorship available"
        ]
    },
    "Canada": {
        "keywords": ["canada", "toronto", "vancouver", "calgary", "montreal", "ottawa", "ontario", "alberta", "british columbia"],
        "sponsorship_indicators": [
            "lmia", "lmia approved", "lmia available", "foreign workers",
            "visa sponsorship", "relocation support", "work permit support"
        ]
    },
    "New Zealand": {
        "keywords": ["new zealand", "auckland", "wellington", "christchurch"],
        "sponsorship_indicators": [
            "accredited employer", "aewv", "work visa support", "relocation package", "visa sponsorship"
        ]
    },
    "Saudi Arabia": {
        "keywords": ["saudi", "riyadh", "jeddah", "khobar", "neom", "red sea", "ksa", "الرياض", "جدة", "السعودية", "الخبر", "نيوم"],
        "sponsorship_indicators": [
            "نقل كفالة", "تأشيرة عمل", "iqama transfer", "work visa", "visa available", "عقد عمل"
        ]
    },
    "Kuwait": {
        "keywords": ["kuwait", "الكويت", "حوّلي", "الأحمدي", "العاصمة"],
        "sponsorship_indicators": [
            "تحويل إقامة", "مادة 18", "transferable visa", "kuwait residency", "visa 18"
        ]
    }
}
