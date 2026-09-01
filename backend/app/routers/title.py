"""职称模块路由：列表 / 增删改查 / 枚举 / 证书。"""
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import EmployeeTitle, TitleCertificate, FileStorage, SysUser, AuditLog
from app.schemas import TitleCreate, TitleUpdate, TitleOut
from app.security import get_current_user
from app.config import UPLOAD_DIR
import json

router = APIRouter(prefix="/api/title", tags=["title"])

# 职称枚举（对应 职称汇总表 Sheet3 分组）
TITLE_SERIES = {
    "engineering": {
        "label": "工程类",
        "levels": [
            {"value": "sub_senior", "label": "高级工程师"},
            {"value": "middle", "label": "工程师"},
            {"value": "junior", "label": "助理工程师"},
            {"value": "junior_researcher", "label": "助理研究员"},
        ]
    },
    "technician": {
        "label": "技能类",
        "levels": [
            {"value": "level_1", "label": "一级（高级技师）"},
            {"value": "level_2", "label": "二级（技师）"},
            {"value": "level_3", "label": "三级（高级工）"},
        ]
    },
}


@router.get("/options")
def get_options():
    """返回序列/等级枚举，供前端筛选和表单使用。"""
    return TITLE_SERIES


@router.get("/list", response_model=list[TitleOut])
def list_titles(
    series: Optional[str] = None,
    level: Optional[str] = None,
    education: Optional[str] = None,
    year: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    q = db.query(EmployeeTitle).filter(EmployeeTitle.is_deleted == False)
    if series:
        q = q.filter(EmployeeTitle.title_series == series)
    if level:
        q = q.filter(EmployeeTitle.title_level == level)
    if education:
        q = q.filter(EmployeeTitle.education == education)
    if year:
        # 认定时间按年筛选
        from sqlalchemy import extract
        q = q.filter(extract('year', EmployeeTitle.title_date) == year)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            (EmployeeTitle.name.like(like)) |
            (EmployeeTitle.major_field.like(like)) |
            (EmployeeTitle.discipline.like(like)) |
            (EmployeeTitle.title_name.like(like))
        )
    return q.order_by(EmployeeTitle.seq_no.asc(), EmployeeTitle.id.asc()).all()


@router.get("/certificates/{title_id}")
def list_certificates(title_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """获取某职称记录的证书列表。"""
    certs = db.query(TitleCertificate).filter(TitleCertificate.title_id == title_id).all()
    result = []
    for c in certs:
        f = db.query(FileStorage).filter(FileStorage.id == c.file_id).first()
        result.append({
            "id": c.id,
            "cert_type": c.cert_type,
            "file_id": c.file_id,
            "original_name": f.original_name if f else "",
            "url": f"/uploads/{Path(f.storage_path).name}" if f else "",
            "created_at": c.created_at,
        })
    return result


@router.post("/certificates/{title_id}")
async def upload_certificate(
    title_id: int,
    file: UploadFile = File(...),
    cert_type: str = Form("职称证书"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """上传职称证书文件，归档到 title_certificate + file_storage。"""
    t = db.query(EmployeeTitle).filter(EmployeeTitle.id == title_id, EmployeeTitle.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="职称记录不存在")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    content = await file.read()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / stored_name
    with open(dest, "wb") as f:
        f.write(content)

    rec = FileStorage(
        original_name=file.filename,
        storage_path=stored_name,
        file_type="pdf" if ext == "pdf" else ("image" if ext in ("jpg", "jpeg", "png") else "other"),
        file_size=len(content),
        mime_type=file.content_type,
        business_type="title_certificate",
        business_id=title_id,
        uploaded_by=current_user.id,
    )
    db.add(rec)
    db.flush()

    cert = TitleCertificate(title_id=title_id, file_id=rec.id, cert_type=cert_type)
    db.add(cert)
    db.commit()

    return {"id": cert.id, "file_id": rec.id, "original_name": rec.original_name, "url": f"/uploads/{stored_name}"}


@router.delete("/certificates/{cert_id}")
def delete_certificate(cert_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    cert = db.query(TitleCertificate).filter(TitleCertificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="证书不存在")
    db.delete(cert)
    db.commit()
    return {"message": "证书已删除"}


@router.get("/{title_id}", response_model=TitleOut)
def get_title(title_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(EmployeeTitle).filter(EmployeeTitle.id == title_id, EmployeeTitle.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="职称记录不存在")
    return t


@router.post("", response_model=TitleOut)
def create_title(req: TitleCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = EmployeeTitle(**req.model_dump(), created_by=current_user.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    _log(db, current_user, "create", "title", t.id, after=req.model_dump())
    return t


@router.put("/{title_id}", response_model=TitleOut)
def update_title(title_id: int, req: TitleUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(EmployeeTitle).filter(EmployeeTitle.id == title_id, EmployeeTitle.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="职称记录不存在")
    before = {c: getattr(t, c) for c in ("name", "title_name", "title_series", "title_level")}
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    _log(db, current_user, "update", "title", t.id, before=before, after=req.model_dump(exclude_unset=True))
    return t


@router.delete("/{title_id}")
def delete_title(title_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    t = db.query(EmployeeTitle).filter(EmployeeTitle.id == title_id, EmployeeTitle.is_deleted == False).first()
    if not t:
        raise HTTPException(status_code=404, detail="职称记录不存在")
    t.is_deleted = True
    db.commit()
    _log(db, current_user, "delete", "title", t.id, before={"name": t.name})
    return {"message": "删除成功"}


def _log(db: Session, user: SysUser, action: str, btype: str, bid: int, before=None, after=None):
    log = AuditLog(
        user_id=user.id, user_name=user.display_name,
        action=action, business_type=btype, business_id=bid,
        before_value=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_value=json.dumps(after, ensure_ascii=False, default=str) if after else None,
    )
    db.add(log)
    db.commit()
