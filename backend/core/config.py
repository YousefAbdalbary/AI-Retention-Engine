import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load CRM & API keys from .env file
load_dotenv()

# Directories & Constants
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BASE_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

MODEL_FILE = "ai_retention_xgboost_optimized.json"
OPTIMAL_THRESHOLD = 0.633
VIP_PLAN_PRICE = 500
CUSTOMER_COUNT = 3200

# LLM Config
LLAMA_API_KEY = os.environ.get("LLAMA_API_KEY", "")
LLAMA_API_URL = os.environ.get(
    "LLAMA_API_URL", "https://api.groq.com/openai/v1/chat/completions"
)
LLAMA_MODEL_NAME = os.environ.get("LLAMA_MODEL_NAME", "llama-3.3-70b-versatile")

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("enterprise-retention-ai")
