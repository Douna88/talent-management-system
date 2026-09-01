"""人才账号模块路由：数币/普通账户，加密存储 + 脱敏展示。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import TalentAccount, SysUser, AuditLog
from app.schemas import TalentAccountCreate, TalentAccountUpdate, TalentAccountOut
from app.security import get_current_user
from app.encryption import encrypt_text, decrypt_text, mask_account
import json

router = APIRouter(prefix="/api/account", tags=["talent_account"])


@router.get("/list", response_model=list[TalentAccountOut])
def list_accounts(
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    q = db.query(TalentAccount).filter(TalentAccount.is_deleted == False)
    if keyword:
        q = q.filter(TalentAccount.name.like(f"%{keyword}%"))
    return q.order_by(TalentAccount.id.asc()).all()


@router.get("/{account_id}", response_model=TalentAccountOut)
def get_account(account_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(TalentAccount).filter(TalentAccount.id == account_id, TalentAccount.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号记录不存在")
    return a


@router.get("/{account_id}/full")
def get_account_full(account_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """返回完整账号（解密），需二次确认后由前端调用。"""
    a = db.query(TalentAccount).filter(TalentAccount.id == account_id, TalentAccount.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号记录不存在")
    return {
        "id": a.id,
        "name": a.name,
        "digital_bank": a.digital_bank,
        "digital_account": decrypt_text(a.digital_account_encrypted),
        "bank_name": a.bank_name,
        "bank_account": decrypt_text(a.bank_account_encrypted),
    }


@router.post("", response_model=TalentAccountOut)
def create_account(req: TalentAccountCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = TalentAccount(
        name=req.name,
        digital_bank=req.digital_bank,
        digital_account_encrypted=encrypt_text(req.digital_account or ""),
        digital_account_mask=mask_account(req.digital_account or ""),
        bank_name=req.bank_name,
        bank_account_encrypted=encrypt_text(req.bank_account or ""),
        bank_account_mask=mask_account(req.bank_account or ""),
        has_subsidy=req.has_subsidy,
        remark=req.remark,
        created_by=current_user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    _log(db, current_user, "create", "talent_account", a.id, after={"name": req.name})
    return a


@router.put("/{account_id}", response_model=TalentAccountOut)
def update_account(account_id: int, req: TalentAccountUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(TalentAccount).filter(TalentAccount.id == account_id, TalentAccount.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号记录不存在")

    if req.name is not None:
        a.name = req.name
    if req.digital_bank is not None:
        a.digital_bank = req.digital_bank
    if req.digital_account is not None:
        a.digital_account_encrypted = encrypt_text(req.digital_account)
        a.digital_account_mask = mask_account(req.digital_account)
    if req.bank_name is not None:
        a.bank_name = req.bank_name
    if req.bank_account is not None:
        a.bank_account_encrypted = encrypt_text(req.bank_account)
        a.bank_account_mask = mask_account(req.bank_account)
    if req.has_subsidy is not None:
        a.has_subsidy = req.has_subsidy
    if req.remark is not None:
        a.remark = req.remark

    db.commit()
    db.refresh(a)
    _log(db, current_user, "update", "talent_account", a.id, after={"name": a.name})
    return a


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    a = db.query(TalentAccount).filter(TalentAccount.id == account_id, TalentAccount.is_deleted == False).first()
    if not a:
        raise HTTPException(status_code=404, detail="账号记录不存在")
    a.is_deleted = True
    db.commit()
    _log(db, current_user, "delete", "talent_account", a.id, before={"name": a.name})
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
