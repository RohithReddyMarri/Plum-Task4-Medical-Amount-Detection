import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Plum Medical Amount Detection Service"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "AI-Powered amount detection, OCR normalization, and context classification for medical bills."
    
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # OCR / Guardrail Thresholds
    OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", 0.40))
    NOISY_DOCUMENT_THRESHOLD: float = float(os.getenv("NOISY_DOCUMENT_THRESHOLD", 0.30))

settings = Settings()
