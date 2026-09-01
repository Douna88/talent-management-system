"""Auth router: login, current user, password change."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SysUser, AuditLog
from app.schemas import LoginRequest, TokenResponse, UserOut, PasswordChange
from app.security import (
    verify_password, hash_password, create_access_token,
    get_current_user
)
import json

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(SysUser).filter(SysUser.username == req.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=423, detail="账号已被锁定，请30分钟后再试")

    if not verify_password(req.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now()
    db.commit()

    log = AuditLog(user_id=user.id, user_name=user.display_name,
                   action="login", business_type="auth")
    db.add(log)
    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: SysUser = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(
    req: PasswordChange,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少8位，需含大小写字母和数字")

    current_user.password_hash = hash_password(req.new_password)
    db.commit()

    log = AuditLog(user_id=current_user.id, user_name=current_user.display_name,
                   action="update", business_type="auth",
                   after_value=json.dumps({"action": "change_password"}, ensure_ascii=False))
    db.add(log)
    db.commit()

    return {"message": "密码修改成功"}
