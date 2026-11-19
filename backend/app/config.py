import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve path to backend/.env
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    OPENALEX_EMAIL: str = os.getenv("OPENALEX_EMAIL", "")


settings = Settings()

GEMINI_API_KEY = settings.GEMINI_API_KEY
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
OPENALEX_EMAIL = settings.OPENALEX_EMAIL
