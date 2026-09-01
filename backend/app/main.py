"""FastAPI main application for the talent management system."""
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, engine
from app.routers import auth, title, talent_account, subsidy, files, stats, ai_query, export, report, import_router
from app.config import UPLOAD_DIR
import app.models  # noqa: F401  (ensure all models are registered)

app = FastAPI(
    title="人才管理系统",
    description="职称管理 + 人才账号 + 个人补贴管理（独立系统）",
    version="1.0.0",
)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(title.router)
app.include_router(talent_account.router)
app.include_router(subsidy.router)
app.include_router(files.router)
app.include_router(stats.router)
app.include_router(ai_query.router)
app.include_router(export.router)
app.include_router(report.router)
app.include_router(import_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "人才管理系统"}


# Serve uploaded files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ---- 伺服构建后的前端（单进程生产部署，VM 上无需 Node）----
# 前端构建产物放 backend/static（vite build outDir）
from app.config import BASE_DIR
FRONTEND_DIST = BASE_DIR / "static"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API / uploads / assets / docs 各自处理 404
        if full_path.startswith(("api/", "uploads/", "assets/", "docs", "openapi.json", "redoc")):
            raise HTTPException(status_code=404)
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        raise HTTPException(status_code=404)
