import os
from pathlib import Path
from dotenv import load_dotenv


# ==============================
# Project paths
# ==============================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
TEMPLATES_DIR = BASE_DIR / "templates"
CACHE_DIR = DATA_DIR / "cache"

APPS_FILE = DATA_DIR / "apps.json"
DATABASE_PATH = DATA_DIR / "toolkit_radar.db"

CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ==============================
# Environment variables
# ==============================

load_dotenv(BASE_DIR / ".env", override=True)

COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_AUTH_CONFIG_ID = os.getenv(
    "TAVILY_AUTH_CONFIG_ID", ""
)
TAVILY_CONNECTED_ACCOUNT_ID = os.getenv(
    "TAVILY_CONNECTED_ACCOUNT_ID", ""
)


# ==============================
# Composio configuration
# ==============================

COMPOSIO_USER_ID = "toolkit-radar"
TAVILY_TOOL_VERSION = "20261103_00"


# ==============================
# Research configuration
# ==============================

MAX_CONCURRENCY = 3
MAX_RESEARCH_ATTEMPTS = 3
REQUEST_TIMEOUT = 30


# ==============================
# Discovery configuration
# ==============================

SEARCH_RESULTS_PER_QUERY = 4
MAX_DOCUMENTS_PER_APP = 8
SEARCH_CACHE_TTL = 86400
MAX_DOCUMENT_CHARS = 100000


GEMINI_API_VERSION = "v1beta"








MAX_CORRECTIVE_QUERIES = 4
MAX_CORRECTIVE_DOCUMENTS = 4
MAX_MERGED_DOCUMENTS = 10

BATCH_CONCURRENCY = 2
BATCH_MAX_ATTEMPTS = 2
MAX_CONSECUTIVE_FAILURES = 3

# Active LLM configuration
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_RESEARCH_MODEL = "gemini-3.1-flash-lite"
GEMINI_VERIFICATION_MODEL = "gemini-3.1-flash-lite"
MAX_CONTEXT_CHARS = 30000
MAX_SOURCE_CHARS = 4500
MAX_OUTPUT_TOKENS = 8192
LLM_MAX_CONCURRENCY = 1
LLM_MAX_RETRIES = 2
