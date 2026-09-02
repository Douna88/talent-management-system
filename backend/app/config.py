"""Application configuration for the talent management system."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database: SQLite for local deployment
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'talent.db'}")

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-please-set-SECRET_KEY-env-var")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Field-level encryption (bank account / digital RMB account)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", SECRET_KEY)

# File upload
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def resolve_upload_path(storage_path):
    """解析 file_storage.storage_path 为真实磁盘路径。

    新数据存相对路径（uploads/ 内的相对路径，跨机器部署不断链）；
    老数据存绝对路径 → 原样返回（兼容）。"""
    p = Path(storage_path)
    if p.is_absolute():
        return p
    return UPLOAD_DIR / p

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "jpg", "jpeg", "png", "svg", "zip", "txt", "csv"
}

# ===== AI service (three-mode switch, v2.2) =====
# AI_PROVIDER: "none" (off) / "local" (intranet LLM) / "cloud" (cloud LLM)
# 内网本地大模型（IT 提供，OpenAI 兼容，免鉴权）
AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() in ("1", "true", "yes")
AI_PROVIDER = os.getenv("AI_PROVIDER", "local")  # none / local / cloud
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:8000/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "")  # 内网免鉴权，留空
AI_MODEL = os.getenv("AI_MODEL", "RadixArk/Qwen3.8-27B-NVFP4")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))  # 秒
