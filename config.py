import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # AssemblyAI
    ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # RAG-Z API
    RAG_Z_API_URL = os.getenv("RAG_Z_API_URL", "http://192.168.0.74:8000")
    RAG_Z_TIMEOUT = int(os.getenv("RAG_Z_TIMEOUT", 30))
    RAG_Z_ENABLED = os.getenv("RAG_Z_ENABLED", "true").lower() == "true"

    # Redis (suporta REDIS_URL do .env ou monta a partir de host/port)
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # Flask
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    PORT = int(os.getenv("PORT", 5358))

    # File handling
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 5368709120))  # 5GB
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    PROCESSED_FOLDER = os.getenv("PROCESSED_FOLDER", "processed")
    ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "flac", "ogg", "webm"}

    # Cache / TTL
    RESULT_CACHE_TTL = 48 * 3600  # 48 hours in seconds
    TEMP_FILE_TTL = 24 * 3600  # 24 hours in seconds
    TRANSCRIPTION_TTL = 72 * 3600  # 72 hours – transcription & ata data in Redis
