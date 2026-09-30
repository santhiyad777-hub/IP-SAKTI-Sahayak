"""Configuration for the existing Streamlit/Ollama/MiniLM/Chroma application."""
import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-oss:120b")
UPLOAD_FOLDER = str(BASE_DIR / "uploaded_documents")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(BASE_DIR / "chroma_db"))
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CORPUS_COLLECTION = "ip_sakti_v1"
RETRIEVAL_K = 8
MIN_SEMANTIC_SCORE = float(os.getenv("MIN_SEMANTIC_SCORE", "0.30"))
