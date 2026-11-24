import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
TEMPLATES_DIR = BASE_DIR / "templates"
CACHE_DIR = BASE_DIR / "cache"

APPS_FILE = DATA_DIR / "apps.json"
DATABASE_PATH = DATA_DIR / "research.db"

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "3"))

MAX_RESEARCH_ATTEMPTS = int(
    os.getenv("MAX_RESEARCH_ATTEMPTS", "3")
)

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))