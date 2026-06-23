import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).parent
DATA_DIR = ROOT_DIR / "data"
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", DATA_DIR / "chroma_db"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "deepseek_rag")
MODEL_VERSION = os.getenv("MODEL_VERSION", "deepseek-r1:1.5b")
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.7))
RAG_ENABLED_DEFAULT = os.getenv("RAG_ENABLED", "true").lower() in ["1", "true", "yes"]
USE_WEB_SEARCH_DEFAULT = os.getenv("USE_WEB_SEARCH", "false").lower() in ["1", "true", "yes"]
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY is required. Set it in your environment or .env file.")
