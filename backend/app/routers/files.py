"""文件中心：统一查询已上传 / 系统文件（职称证书、政策文档、AI 附件等）。"""
import shutil
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.database import get_db
from app.models import FileStorage, SysUser
from app.security import get_current_user
from app import config

router = APIRouter(prefix="/api/files", tags=["files"])

BUSINESS_LABELS = {
    "title_certificate": "职称证书",
    "subsidy_policy": "政策文档",
    "subsidy_voucher": "发放凭证",
    "ai_chat": "AI 对话附件",
    "other": "其他文档",
}

# 业务类型 -> 实际文件落盘目录（与上传/存储一致）
BUSINESS_DIRS = {
    "title_certificate": "certificates",
    "subsidy_policy": "policy",
    "ai_chat": "ai",
    "subsidy_voucher": "vouchers",
    "other": "others",
}

# 文件中心允许上传的扩展名（含 Word / PDF / Excel / PPT / 图片）
ALLOWED_EXT = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "png", "jpg", "jpeg", "gif", "bmp", "webp",
}


@router.post("/upload")
def upload_file(
    business_type: str = Form("other"),
    business_id: int = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """通用文档上传：把文件落盘到 uploads/<业务目录>/ 并在 file_storage 登记，供文件中心统一管理。"""
    if business_type not in BUSINESS_DIRS:
        raise HTTPException(status_code=400, detail=f"不支持的业务类型：{business_type}")
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：.{ext or '未知'}（允许 PDF/Word/Excel/PPT/图片）")
    dest_dir = config.UPLOAD_DIR / BUSINESS_DIRS[business_type]
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = dest_dir / f"{uuid.uuid4().hex}_{file.filename}"
    with saved.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    ftype = "image" if ext in ("png", "jpg", "jpeg", "gif", "bmp", "webp") else (
        "word" if ext in ("doc", "docx") else "pdf" if ext == "pdf" else "excel" if ext in ("xls", "xlsx") else "other")
    fstore = FileStorage(
        original_name=file.filename,
        storage_path=str(saved.relative_to(config.UPLOAD_DIR)).replace("\\", "/"),
        file_type=ftype, file_size=saved.stat().st_size, mime_type=file.content_type,
        business_type=business_type, business_id=business_id, uploaded_by=current_user.id,
    )
    db.add(fstore)
    db.commit()
    db.refresh(fstore)
    return {
        "ok": True, "id": fstore.id, "name": fstore.original_name, "size": fstore.file_size,
        "business_type": business_type, "business_label": BUSINESS_LABELS.get(business_type, business_type),
        "uploaded_at": fstore.uploaded_at.strftime("%Y-%m-%d %H:%M") if fstore.uploaded_at else "",
    }



@router.get("")
def list_files(
    business_type: str = Query(None),
    keyword: str = Query(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """列出文件中心所有文件（可按业务类型 / 关键字过滤）。"""
    q = db.query(FileStorage)
    if business_type:
        q = q.filter(FileStorage.business_type == business_type)
    if keyword:
        q = q.filter(FileStorage.original_name.like(f"%{keyword}%"))
    rows = q.order_by(FileStorage.uploaded_at.desc()).limit(500).all()
    return [{
        "id": f.id,
        "name": f.original_name,
        "type": f.file_type,
        "business_type": f.business_type,
        "business_label": BUSINESS_LABELS.get(f.business_type, f.business_type or "其他"),
        "business_id": f.business_id,
        "size": f.file_size,
        "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d %H:%M") if f.uploaded_at else "",
        "uploader": f.uploaded_by,
    } for f in rows]


@router.get("/download/{file_id}")
def download_file(file_id: int, db: Session = Depends(get_db),
                 current_user: SysUser = Depends(get_current_user)):
    """下载 / 预览文件。"""
    f = db.query(FileStorage).filter(FileStorage.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    p = config.resolve_upload_path(f.storage_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="文件已被移出磁盘")
    return FileResponse(str(p), filename=f.original_name)
