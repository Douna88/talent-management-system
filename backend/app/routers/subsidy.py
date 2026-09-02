"""补贴政策路由：16 个政策 CRUD + 预置种子数据 + 明细查询 + 发放确认流程。

发放状态流转：
    pending（已记录待打款）
      → pending_confirm（待部门员工确认）
      → confirmed（员工已确认）/ rejected（有异议，退回）
      → paid（财务实际发放）
"""
import os
import re
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from app.database import get_db
from app.models import (
    SubsidyPolicy, SubsidyApplication, SubsidyPayment, PaymentComment,
    SysUser, AuditLog, SubsidyRule, FileStorage
)
from app.schemas import PolicyCreate, PolicyUpdate, PolicyOut
from app.security import get_current_user
from app import ai_bridge, config
import json

router = APIRouter(prefix="/api/subsidy", tags=["subsidy"])

# 批量扫描目录（政策 PDF/文档 所在根目录）
POLICY_SCAN_ROOT = Path(r"D:\IP workflow\人才补贴明细")

# 已计入"累计到账"的状态
DONE_STATUSES = ("paid", "confirmed", "completed")

# 16 个政策（对应 D:\IP workflow\人才补贴明细\ 下文件夹）
SEED_POLICIES = [
    {"policy_name": "2021-2023相城区重点产业人才计划-薪酬补贴", "policy_category": "薪酬补贴", "region": "相城区", "region_level": "区级"},
    {"policy_name": "2024-2026相城区重点产业人才计划-薪酬补贴", "policy_category": "薪酬补贴", "region": "相城区", "region_level": "区级"},
    {"policy_name": "高铁新城顶尖高校毕业生就业创业奖励补贴", "policy_category": "就业创业", "region": "高铁新城", "region_level": "县级"},
    {"policy_name": "环秀湖产业紧缺专技人才计划", "policy_category": "紧缺专技", "region": "相城区", "region_level": "区级"},
    {"policy_name": "苏州高铁新城人才租房补贴", "policy_category": "租房", "region": "高铁新城", "region_level": "县级"},
    {"policy_name": "苏州市高端人才奖励计划", "policy_category": "奖励", "region": "苏州市", "region_level": "市级"},
    {"policy_name": "苏州市人才乐居租房贴", "policy_category": "租房", "region": "苏州市", "region_level": "市级"},
    {"policy_name": "苏州市优秀人才专项", "policy_category": "专项", "region": "苏州市", "region_level": "市级"},
    {"policy_name": "苏州市重点产业紧缺人才计划", "policy_category": "紧缺人才", "region": "苏州市", "region_level": "市级"},
    {"policy_name": "相城区产业人才专项奖励", "policy_category": "奖励", "region": "相城区", "region_level": "区级"},
    {"policy_name": "相城区紧缺专技人才计划", "policy_category": "紧缺专技", "region": "相城区", "region_level": "区级"},
    {"policy_name": "相城区名校优生落户奖励", "policy_category": "落户", "region": "相城区", "region_level": "区级"},
    {"policy_name": "相城区人才贡献奖励", "policy_category": "贡献", "region": "相城区", "region_level": "区级"},
    {"policy_name": "相城区人才乐居补贴", "policy_category": "乐居", "region": "相城区", "region_level": "区级"},
    {"policy_name": "相城区重点产业人才计划-安家补贴", "policy_category": "安家", "region": "相城区", "region_level": "区级"},
    {"policy_name": "应届高校毕业生租房补贴", "policy_category": "租房", "region": "苏州市", "region_level": "市级"},
]


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    return db.query(SubsidyPolicy).filter(SubsidyPolicy.is_deleted == False).order_by(SubsidyPolicy.id.asc()).all()


@router.post("/policies", response_model=PolicyOut)
def create_policy(req: PolicyCreate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    p = SubsidyPolicy(**req.model_dump(), created_by=current_user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    _log(db, current_user, "create", "subsidy_policy", p.id, after={"policy_name": p.policy_name})
    return p


@router.put("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: int, req: PolicyUpdate, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    p = db.query(SubsidyPolicy).filter(SubsidyPolicy.id == policy_id, SubsidyPolicy.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="政策不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    _log(db, current_user, "update", "subsidy_policy", p.id, after={"policy_name": p.policy_name})
    return p


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    p = db.query(SubsidyPolicy).filter(SubsidyPolicy.id == policy_id, SubsidyPolicy.is_deleted == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="政策不存在")
    p.is_deleted = True
    db.commit()
    _log(db, current_user, "delete", "subsidy_policy", p.id, before={"policy_name": p.policy_name})
    return {"message": "删除成功"}


@router.post("/policies/seed")
def seed_policies(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """一键预置 16 个政策（幂等：已存在的跳过）。"""
    existing = {p.policy_name for p in db.query(SubsidyPolicy).all()}
    created = 0
    for item in SEED_POLICIES:
        if item["policy_name"] in existing:
            continue
        p = SubsidyPolicy(**item, folder_name=item["policy_name"], created_by=current_user.id)
        db.add(p)
        created += 1
    db.commit()
    _log(db, current_user, "create", "subsidy_policy", 0, after={"seeded": created})
    return {"message": f"已预置 {created} 个政策（共 {len(SEED_POLICIES)} 个）"}


@router.get("/applications")
def list_applications(
    policy_id: Optional[int] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """申领列表（含政策名 + 发放笔数 + 批注数）。"""
    q = db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False)
    if policy_id:
        q = q.filter(SubsidyApplication.policy_id == policy_id)
    if status:
        q = q.filter(SubsidyApplication.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter((SubsidyApplication.name.like(like)) | (SubsidyApplication.bu.like(like)) | (SubsidyApplication.department.like(like)))
    apps = q.order_by(SubsidyApplication.id.asc()).all()

    result = []
    for a in apps:
        policy = db.query(SubsidyPolicy).filter(SubsidyPolicy.id == a.policy_id).first()
        payments = db.query(SubsidyPayment).filter(SubsidyPayment.application_id == a.id).all()
        comment_count = db.query(PaymentComment).join(SubsidyPayment).filter(SubsidyPayment.application_id == a.id).count()
        result.append({
            "id": a.id,
            "policy_id": a.policy_id,
            "policy_name": policy.policy_name if policy else "",
            "name": a.name,
            "bu": a.bu,
            "department": a.department,
            "awarded_date": a.awarded_date.strftime("%Y.%m.%d") if a.awarded_date else "",
            "award_level": a.award_level,
            "total_expected": a.total_expected,
            "total_received": a.total_received,
            "payment_count": len(payments),
            "comment_count": comment_count,
            "status": a.status,
            "remark": a.remark,
        })
    return result


@router.get("/applications/{app_id}/payments")
def get_payments(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """某申领的发放明细 + 批注。"""
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="申领记录不存在")
    payments = db.query(SubsidyPayment).filter(SubsidyPayment.application_id == app_id)\
        .order_by(SubsidyPayment.payment_index.asc()).all()
    result = []
    for p in payments:
        comments = db.query(PaymentComment).filter(PaymentComment.payment_id == p.id).all()
        result.append({
            "id": p.id,
            "payment_index": p.payment_index,
            "expected_date": p.expected_date.strftime("%Y.%m.%d") if p.expected_date else "",
            "actual_date": p.actual_date.strftime("%Y.%m.%d") if p.actual_date else "",
            "amount": p.amount,
            "status": p.status,
            "conflict_flag": p.conflict_flag,
            "remark": p.remark,
            "comments": [{"author": c.author, "content": c.content, "source": c.source} for c in comments],
        })
    return result


# ============================================================
# 发放确认流程
# ============================================================
STATUS_LABELS = {
    "pending": "待发放",
    "pending_confirm": "待确认",
    "confirmed": "已确认",
    "paid": "已发放",
    "rejected": "有异议",
    "stopped": "已中止",
    "unpaid": "未发放",
    "completed": "已完成",
}


def _parse_date(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _recalc_received(db: Session, app: SubsidyApplication):
    """重算某申领的累计到账（只累计已确认/已发放的部分）。"""
    if not app:
        return
    total = db.query(SubsidyPayment).filter(
        SubsidyPayment.application_id == app.id,
        SubsidyPayment.status.in_(DONE_STATUSES),
    ).with_entities(SubsidyPayment.amount).all()
    app.total_received = round(sum((a[0] or 0) for a in total), 2)


def _payment_row(p: SubsidyPayment, db: Session):
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == p.application_id).first()
    policy = db.query(SubsidyPolicy).filter(SubsidyPolicy.id == app.policy_id).first() if app else None
    comments = db.query(PaymentComment).filter(PaymentComment.payment_id == p.id).all()
    return {
        "id": p.id,
        "application_id": p.application_id,
        "name": app.name if app else "",
        "bu": app.bu if app else "",
        "department": app.department if app else "",
        "policy_id": app.policy_id if app else None,
        "policy_name": policy.policy_name if policy else "",
        "payment_index": p.payment_index,
        "expected_date": p.expected_date.strftime("%Y.%m.%d") if p.expected_date else "",
        "actual_date": p.actual_date.strftime("%Y.%m.%d") if p.actual_date else "",
        "amount": p.amount,
        "status": p.status,
        "status_label": STATUS_LABELS.get(p.status, p.status),
        "conflict_flag": p.conflict_flag,
        "remark": p.remark,
        "comments": [{"author": c.author, "content": c.content, "source": c.source} for c in comments],
    }


@router.get("/payments")
def list_payments(
    status: Optional[str] = None,
    policy_id: Optional[int] = None,
    keyword: Optional[str] = None,
    year: Optional[str] = None,
    limit: int = Query(500, le=2000),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """发放明细列表（默认看待确认 + 有异议 + 已确认）。"""
    q = db.query(SubsidyPayment).join(
        SubsidyApplication, SubsidyApplication.id == SubsidyPayment.application_id, isouter=True)
    if status:
        q = q.filter(SubsidyPayment.status.in_(status.split(",")))
    else:
        q = q.filter(SubsidyPayment.status.in_(("pending_confirm", "rejected", "confirmed")))
    if policy_id:
        q = q.filter(SubsidyApplication.policy_id == policy_id)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(SubsidyApplication.name.like(like))
    if year:
        q = q.filter(
            (SubsidyPayment.actual_date.isnot(None) & (SubsidyPayment.actual_date >= f"{year}-01-01")
             & (SubsidyPayment.actual_date <= f"{year}-12-31"))
            | (SubsidyPayment.actual_date.is_(None) & SubsidyPayment.expected_date.isnot(None)
               & (SubsidyPayment.expected_date >= f"{year}-01-01")
               & (SubsidyPayment.expected_date <= f"{year}-12-31"))
        )
    rows = q.order_by(SubsidyPayment.id.desc()).limit(limit).all()
    return [_payment_row(p, db) for p in rows]


@router.get("/payments/summary")
def payments_summary(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """确认工作台顶部卡片数据。"""
    from sqlalchemy import func
    by_status = dict(db.query(SubsidyPayment.status, func.count(SubsidyPayment.id))
                     .group_by(SubsidyPayment.status).all())
    pending = db.query(func.count(SubsidyPayment.id), func.coalesce(func.sum(SubsidyPayment.amount), 0))\
        .filter(SubsidyPayment.status == "pending_confirm").first()
    rejected = db.query(func.count(SubsidyPayment.id), func.coalesce(func.sum(SubsidyPayment.amount), 0))\
        .filter(SubsidyPayment.status == "rejected").first()
    this_year = str(date.today().year)
    confirmed_y = db.query(func.count(SubsidyPayment.id), func.coalesce(func.sum(SubsidyPayment.amount), 0))\
        .filter(SubsidyPayment.status.in_(("confirmed", "paid")),
                SubsidyPayment.actual_date >= f"{this_year}-01-01").first()
    return {
        "pending_count": pending[0] or 0,
        "pending_amount": round(pending[1] or 0, 2),
        "rejected_count": rejected[0] or 0,
        "rejected_amount": round(rejected[1] or 0, 2),
        "confirmed_year_count": confirmed_y[0] or 0,
        "confirmed_year_amount": round(confirmed_y[1] or 0, 2),
        "by_status": {k: v for k, v in by_status.items()},
        "status_labels": STATUS_LABELS,
    }


class PaymentCreate(BaseModel):
    application_id: int
    payment_index: int
    expected_date: Optional[str] = None
    actual_date: Optional[str] = None
    amount: float
    status: str = "pending_confirm"
    remark: Optional[str] = None


@router.post("/payments")
def create_payment(req: PaymentCreate, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    """新增一笔发放（默认进入"待部门员工确认"）。"""
    app = db.query(SubsidyApplication).filter(
        SubsidyApplication.id == req.application_id, SubsidyApplication.is_deleted == False).first()
    if not app:
        raise HTTPException(status_code=404, detail="申领记录不存在")
    dup = db.query(SubsidyPayment).filter(
        SubsidyPayment.application_id == req.application_id,
        SubsidyPayment.payment_index == req.payment_index).first()
    if dup:
        raise HTTPException(status_code=400, detail=f"该申领已有第 {req.payment_index} 期发放记录")

    p = SubsidyPayment(
        application_id=req.application_id,
        payment_index=req.payment_index,
        expected_date=_parse_date(req.expected_date),
        actual_date=_parse_date(req.actual_date),
        amount=req.amount,
        status=req.status or "pending_confirm",
        remark=req.remark,
        created_by=current_user.id,
    )
    db.add(p)
    if p.status in DONE_STATUSES:
        _recalc_received(db, app)
    _log(db, current_user, "create", "subsidy_payment", p.id,
         after={"name": app.name, "index": p.payment_index, "amount": p.amount, "status": p.status})
    db.commit()
    db.refresh(p)
    return _payment_row(p, db)


class ConfirmRequest(BaseModel):
    remark: Optional[str] = None
    actual_date: Optional[str] = None
    set_paid: bool = False


def _apply_confirm(p: SubsidyPayment, req: ConfirmRequest, user: SysUser, db: Session) -> dict:
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == p.application_id).first()
    before = {"status": p.status, "amount": p.amount, "remark": p.remark}
    p.status = "paid" if req.set_paid else "confirmed"
    if req.actual_date:
        p.actual_date = _parse_date(req.actual_date)
    elif not p.actual_date:
        p.actual_date = date.today()
    if req.remark:
        p.remark = ((p.remark or "") + ("；" if p.remark else "") + f"[确认] {req.remark}").strip("；")
    _recalc_received(db, app)
    _log(db, user, "update", "subsidy_payment", p.id, before=before,
         after={"status": p.status, "remark": p.remark})
    return before


@router.post("/payments/{payment_id}/confirm")
def confirm_payment(payment_id: int, req: ConfirmRequest, db: Session = Depends(get_db),
                    current_user: SysUser = Depends(get_current_user)):
    """部门员工确认这笔发放（可附备注/特殊情况说明）。"""
    p = db.query(SubsidyPayment).filter(SubsidyPayment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="发放记录不存在")
    if p.status in ("paid",):
        raise HTTPException(status_code=400, detail="该笔已发放，无需再确认")
    _apply_confirm(p, req, current_user, db)
    db.commit()
    return {"ok": True, "message": "已确认", "payment": _payment_row(p, db)}


class RejectRequest(BaseModel):
    reason: str


@router.post("/payments/{payment_id}/reject")
def reject_payment(payment_id: int, req: RejectRequest, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    """有异议，退回（必须写明原因）。"""
    p = db.query(SubsidyPayment).filter(SubsidyPayment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="发放记录不存在")
    before = {"status": p.status, "remark": p.remark}
    p.status = "rejected"
    p.remark = ((p.remark or "") + ("；" if p.remark else "") + f"[有异议] {req.reason}").strip("；")
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == p.application_id).first()
    _recalc_received(db, app)
    _log(db, current_user, "update", "subsidy_payment", p.id, before=before,
         after={"status": "rejected", "remark": p.remark})
    db.commit()
    return {"ok": True, "message": "已标记有异议", "payment": _payment_row(p, db)}


class PaymentUpdate(BaseModel):
    """人工订正一笔发放记录：可改 金额 / 备注 / 实发日期 / 期次。
    约定：不传该字段 = 保持不变；传空串/空值 = 清空（备注/实发日期）。"""
    amount: Optional[float] = None
    remark: Optional[str] = None        # "" = 清空备注
    actual_date: Optional[str] = None   # "" = 清空实发日期
    payment_index: Optional[int] = None


@router.put("/payments/{payment_id}")
def update_payment(payment_id: int, req: PaymentUpdate, db: Session = Depends(get_db),
                   current_user: SysUser = Depends(get_current_user)):
    """修改一笔发放记录（金额/备注/实发日期/期次），修改后自动重算累计到账。"""
    p = db.query(SubsidyPayment).filter(SubsidyPayment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="发放记录不存在")
    before = {"amount": p.amount, "remark": p.remark,
              "actual_date": str(p.actual_date) if p.actual_date else None,
              "payment_index": p.payment_index}
    if req.amount is not None:
        if req.amount < 0:
            raise HTTPException(status_code=400, detail="金额不能为负数")
        p.amount = round(req.amount, 2)
    if req.remark is not None:
        p.remark = req.remark.strip() or None
    if req.actual_date is not None:
        p.actual_date = _parse_date(req.actual_date) if req.actual_date else None
    if req.payment_index is not None:
        if req.payment_index < 1:
            raise HTTPException(status_code=400, detail="期次必须 >= 1")
        dup = db.query(SubsidyPayment).filter(
            SubsidyPayment.application_id == p.application_id,
            SubsidyPayment.payment_index == req.payment_index,
            SubsidyPayment.id != p.id).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"该申领已有第 {req.payment_index} 期记录，期次不能重复")
        p.payment_index = req.payment_index
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == p.application_id).first()
    _recalc_received(db, app)
    _log(db, current_user, "update", "subsidy_payment", p.id, before=before,
         after={"amount": p.amount, "remark": p.remark,
                "actual_date": str(p.actual_date) if p.actual_date else None,
                "payment_index": p.payment_index})
    db.commit()
    db.refresh(p)
    return {"ok": True, "message": "已更新", "payment": _payment_row(p, db)}


class BatchConfirmRequest(BaseModel):
    ids: List[int]
    remark: Optional[str] = None
    set_paid: bool = False


@router.post("/payments/batch-confirm")
def batch_confirm(req: BatchConfirmRequest, db: Session = Depends(get_db),
                  current_user: SysUser = Depends(get_current_user)):
    """批量确认。"""
    ok, skipped = 0, 0
    for pid in req.ids:
        p = db.query(SubsidyPayment).filter(SubsidyPayment.id == pid).first()
        if not p or p.status == "paid":
            skipped += 1
            continue
        _apply_confirm(p, ConfirmRequest(remark=req.remark, set_paid=req.set_paid), current_user, db)
        ok += 1
    db.commit()
    return {"ok": True, "confirmed": ok, "skipped": skipped,
            "message": f"已确认 {ok} 笔" + (f"，跳过 {skipped} 笔" if skipped else "")}


def _parse_amount_rule(rule_value: str):
    """从 amount 规则的 rule_value 抽数字（元）。支持 "60000元" / "60000 元/3 期" / "20,000"。"""
    if not rule_value: return None
    s = str(rule_value)
    m = re.search(r'(\d[\d,]*(?:\.\d+)?)', s.replace(',', ''))
    if not m: return None
    try: return float(m.group(1))
    except: return None


def _parse_installment_count(rule_value: str):
    """从 installment 规则抽期数（"分3期"/"3期"/"3"）。"""
    if not rule_value: return None
    s = str(rule_value)
    m = re.search(r'(\d+)', s)
    if not m: return None
    try: return int(m.group(1))
    except: return None


@router.post("/applications/{app_id}/generate-payments")
def generate_payments(app_id: int, only_if_empty: bool = True,
                      db: Session = Depends(get_db),
                      current_user: SysUser = Depends(get_current_user)):
    """按政策规则（installment 期数 + amount 总额）自动计算每期应发金额，生成 SubsidyPayment 记录。
    - 期数 = 政策 installment 规则（如 "分3期" → 3）；缺省视为 1 期一次性发放。
    - 每期金额 = 申领 total_expected / 期数（最后一期取整 + 找零）。
    - 应发日期：从 awarded_date 起每年 +1；如无则取当前日期。
    - 已存在 payment_index 的不重复创建（按 application_id + payment_index 去重）。
    - 状态：pending_confirm（进入「发放确认」页面供用户审核金额）。
    - only_if_empty=True 时，若该申领已有任何发放记录则跳过（避免覆盖已导入的实际数据）。
    """
    app = db.query(SubsidyApplication).filter(
        SubsidyApplication.id == app_id, SubsidyApplication.is_deleted == False).first()
    if not app:
        raise HTTPException(status_code=404, detail="申领记录不存在")
    created = _generate_for_app(app, db, current_user, only_if_empty=only_if_empty)
    return {"ok": True, "generated": len(created),
            "payments": [{"id": p.id, "payment_index": p.payment_index, "amount": p.amount,
                          "expected_date": p.expected_date.isoformat() if p.expected_date else None} for p in created]}


def _generate_for_app(app: SubsidyApplication, db: Session, user: SysUser, only_if_empty: bool = True):
    """核心：按政策规则为单个申领生成应发计划（pending_confirm）。返回新建的 payment 列表。"""
    has_any = db.query(SubsidyPayment).filter(SubsidyPayment.application_id == app.id).first()
    if only_if_empty and has_any:
        return []
    rules = db.query(SubsidyRule).filter(SubsidyRule.policy_id == app.policy_id).all() if app.policy_id else []
    inst_n = 1
    for r in rules:
        if r.rule_type == "installment":
            v = _parse_installment_count(r.rule_value or "")
            if v: inst_n = v
    total = app.total_expected or 0
    if total <= 0 or inst_n <= 0:
        return []
    base = app.awarded_date or date.today()
    per = round(total / inst_n, 2)
    # last period takes the rounding remainder so sum matches total exactly
    amounts = [per] * (inst_n - 1) + [round(total - per * (inst_n - 1), 2)]
    existing = db.query(SubsidyPayment).filter(
        SubsidyPayment.application_id == app.id).all()
    used_idx = {p.payment_index for p in existing}
    created = []
    for i in range(inst_n):
        idx = i + 1
        if idx in used_idx:
            continue
        try:
            ed = date(base.year + i, base.month, base.day) if (1 <= base.month <= 12) else base
        except Exception:
            ed = date(base.year + i, 12, 31)
        p = SubsidyPayment(
            application_id=app.id, payment_index=idx, expected_date=ed,
            amount=amounts[i], status="pending_confirm", created_by=user.id,
        )
        db.add(p)
        created.append(p)
    if created:
        db.flush()
        _log(db, user, "create", "subsidy_payment", 0,
             after={"application_id": app.id, "generated": len(created), "periods": inst_n,
                    "per_amount": per, "total": total})
    return created


def _settle_policy(db: Session, policy_id: int, user: SysUser):
    """政策确认后：为该政策下「尚无发放记录」的申领按规则生成应发计划。返回生成笔数。"""
    apps = db.query(SubsidyApplication).filter(
        SubsidyApplication.policy_id == policy_id, SubsidyApplication.is_deleted == False).all()
    total = 0
    for a in apps:
        total += len(_generate_for_app(a, db, user, only_if_empty=True))
    return total


@router.post("/settle-all")
def settle_all(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """一键为所有「尚无发放记录」的申领按政策规则自动结算（生成应发计划）。"""
    apps = db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all()
    apps_done = 0
    payments = 0
    for a in apps:
        has_any = db.query(SubsidyPayment).filter(SubsidyPayment.application_id == a.id).first()
        if has_any:
            continue
        created = _generate_for_app(a, db, current_user, only_if_empty=True)
        if created:
            apps_done += 1
            payments += len(created)
    db.commit()
    _log(db, current_user, "create", "subsidy_payment", 0,
         after={"settled_apps": apps_done, "generated": payments})
    return {"ok": True, "settled_apps": apps_done, "generated": payments,
            "message": f"已为 {apps_done} 条申领自动结算，生成 {payments} 笔应发计划"}



class CommentCreate(BaseModel):
    content: str
    author: Optional[str] = None


@router.post("/payments/{payment_id}/comments")
def add_comment(payment_id: int, req: CommentCreate, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    """给某笔发放追加批注。"""
    p = db.query(SubsidyPayment).filter(SubsidyPayment.id == payment_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="发放记录不存在")
    c = PaymentComment(
        payment_id=payment_id,
        author=req.author or (current_user.display_name or current_user.username),
        content=req.content, source="manual")
    db.add(c)
    db.commit()
    return {"ok": True, "id": c.id, "message": "批注已添加"}


def _log(db: Session, user: SysUser, action: str, btype: str, bid: int, before=None, after=None):
    log = AuditLog(
        user_id=user.id, user_name=user.display_name,
        action=action, business_type=btype, business_id=bid,
        before_value=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_value=json.dumps(after, ensure_ascii=False, default=str) if after else None,
    )
    db.add(log)
    db.commit()


# ============================================================
# 政策文档上传 / AI 解析 / 批量扫描
# ============================================================
POLICY_DOC_DIR = config.UPLOAD_DIR / "policy"
POLICY_DOC_DIR.mkdir(parents=True, exist_ok=True)
DOC_EXT = {"pdf", "doc", "docx"}


def _extract_doc_text(path: str) -> str:
    """抽取政策文档文本（复用 ai_bridge 的抽取能力）。"""
    return ai_bridge.extract_file_text(path, max_chars=20000)


def _rules_from_json(policy: SubsidyPolicy, rules: dict) -> List[SubsidyRule]:
    """把 AI 解析出的规则 JSON 落库成 subsidy_rule 行。"""
    out = []
    sort = 0

    def add(rtype, rkey, rvalue, desc="", quote=""):
        nonlocal sort
        sort += 1
        out.append(SubsidyRule(
            policy_id=policy.id, rule_type=rtype, rule_key=rkey,
            rule_value=json.dumps(rvalue, ensure_ascii=False) if not isinstance(rvalue, str) else rvalue,
            rule_desc=desc, source_quote=quote, sort_order=sort,
        ))

    if rules.get("valid_from") or rules.get("valid_until"):
        add("period", "valid_period", f"{rules.get('valid_from') or '?'} ~ {rules.get('valid_until') or '?'}")
    if rules.get("target_scope"):
        add("target", "target_scope", rules["target_scope"])
    ps = rules.get("payment_schedule") or {}
    if ps.get("total_amount"):
        add("amount", "total_amount", ps["total_amount"], desc="政策总额")
    for inst in (ps.get("installments") or []):
        add("installment", f"inst_{inst.get('index')}", inst,
            desc=f"第{inst.get('index')}期：{inst.get('amount')}元 / {inst.get('trigger') or '条件未识别'}")
    elig = rules.get("eligibility") or {}
    if elig:
        add("eligibility", "eligibility", elig,
            desc=f"社保{elig.get('social_security_months') or '?'}月 / 仅应届={elig.get('is_graduate_only')} / 补缴不算={elig.get('exclude_backfill_social_security')}")
    for cf in (rules.get("conflict_rules") or []):
        add("conflict", "conflict", cf, desc=f"与「{cf.get('conflict_with')}」{cf.get('action')}")
    for note in (rules.get("special_notes") or []):
        add("special", "special", note)
    return out


@router.post("/policies/{policy_id}/upload-doc")
def upload_policy_doc(
    policy_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """上传一份政策文档（PDF/Word），抽取原文并暂存，等待 AI 解析。"""
    policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.id == policy_id, SubsidyPolicy.is_deleted == False).first()
    if not policy:
        raise HTTPException(status_code=404, detail="政策不存在")
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in DOC_EXT:
        raise HTTPException(status_code=400, detail="仅支持 PDF / DOC / DOCX")
    saved = POLICY_DOC_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    with saved.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    text = _extract_doc_text(str(saved))
    fstore = FileStorage(
        original_name=file.filename,
        storage_path=str(saved.relative_to(config.UPLOAD_DIR)).replace("\\", "/"),
        file_type="word" if ext in ("doc", "docx") else "pdf",
        file_size=saved.stat().st_size, mime_type=file.content_type,
        business_type="subsidy_policy", business_id=policy.id,
        uploaded_by=current_user.id,
    )
    db.add(fstore)
    db.flush()
    policy.source_file_id = fstore.id
    policy.raw_text = text
    policy.ai_status = "pending"
    db.commit()
    return {"ok": True, "text_length": len(text), "preview": text[:600]}


@router.post("/policies/{policy_id}/parse")
def parse_policy_doc(
    policy_id: int,
    force: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """对政策原文做 AI 规则解析，写入 subsidy_rule。force=true 时覆盖既有解析。"""
    policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.id == policy_id, SubsidyPolicy.is_deleted == False).first()
    if not policy:
        raise HTTPException(status_code=404, detail="政策不存在")
    if not policy.raw_text or len(policy.raw_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="请先上传政策文档或填入原文")
    if policy.ai_status == "parsed" and not force:
        return {"ok": True, "skipped": True, "message": "已解析过，传 force=true 可重新解析"}

    parsed = ai_bridge.parse_policy_rules(policy.raw_text)
    if not parsed.get("ok"):
        return {"ok": False, "message": parsed.get("error") or "解析失败", "raw": parsed.get("raw", "")[:500]}

    # 清空旧规则
    db.query(SubsidyRule).filter(SubsidyRule.policy_id == policy.id).delete()
    rules = _rules_from_json(policy, parsed["rules"])
    for r in rules:
        db.add(r)
    policy.ai_status = "parsed"
    db.commit()
    return {"ok": True, "rule_count": len(rules), "message": f"已解析出 {len(rules)} 条规则，请人工确认后生效"}


@router.post("/policies/{policy_id}/confirm-rules")
def confirm_policy_rules(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """人工确认规则生效，并立即按规则为该政策下尚无发放记录的申领自动结算（生成应发计划）。"""
    policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.id == policy_id, SubsidyPolicy.is_deleted == False).first()
    if not policy:
        raise HTTPException(status_code=404, detail="政策不存在")
    if policy.ai_status not in ("parsed", "confirmed"):
        raise HTTPException(status_code=400, detail="请先解析出规则再确认")
    policy.ai_status = "confirmed"
    settled = _settle_policy(db, policy_id, current_user)
    db.commit()
    _log(db, current_user, "update", "subsidy_policy", policy.id,
         after={"ai_status": "confirmed", "auto_settled": settled})
    return {"ok": True, "message": "规则已确认生效", "auto_settled": settled}


@router.post("/policies/batch-confirm-rules")
def batch_confirm_rules(
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """批量确认所有「待确认(parsed)」政策规则，并逐一触发自动结算。一次请求完成。"""
    policies = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status == "parsed").all()
    done, settled, failed = 0, 0, 0
    for p in policies:
        try:
            p.ai_status = "confirmed"
            settled += _settle_policy(db, p.id, current_user)
            done += 1
        except Exception:
            failed += 1
    db.commit()
    _log(db, current_user, "update", "subsidy_policy", 0,
         after={"batch_confirm": done, "auto_settled": settled, "failed": failed})
    return {"ok": True, "confirmed": done, "auto_settled": settled, "failed": failed,
            "message": f"已确认 {done} 个政策，自动结算生成 {settled} 笔应发计划"}



@router.get("/policies/{policy_id}/rules")
def get_policy_rules(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """返回某政策的已解析规则（供发放确认页展示政策依据）。"""
    rules = db.query(SubsidyRule).filter(SubsidyRule.policy_id == policy_id)\
        .order_by(SubsidyRule.sort_order.asc()).all()
    return [{
        "id": r.id, "rule_type": r.rule_type, "rule_key": r.rule_key,
        "rule_value": r.rule_value, "rule_desc": r.rule_desc,
        "source_quote": r.source_quote,
    } for r in rules]


class RuleEdit(BaseModel):
    rule_type: Optional[str] = None
    rule_key: Optional[str] = None
    rule_value: Optional[str] = None
    rule_desc: Optional[str] = None
    source_quote: Optional[str] = None
    sort_order: Optional[int] = None


def _reset_policy_ai_status(db: Session, policy_id: int, user: SysUser):
    """规则被人工增删改后，退回为待确认状态，需重新确认生效。"""
    p = db.query(SubsidyPolicy).filter(SubsidyPolicy.id == policy_id).first()
    if p and p.ai_status == "confirmed":
        p.ai_status = "parsed"
        _log(db, user, "update", "subsidy_policy", policy_id, after={"ai_status": "parsed", "reason": "规则被人工订正"})


@router.post("/policies/{policy_id}/rules")
def create_rule(policy_id: int, req: RuleEdit, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    """人工新增一条政策规则。"""
    if not req.rule_type:
        raise HTTPException(status_code=422, detail="rule_type 必填")
    max_order = db.query(func.coalesce(func.max(SubsidyRule.sort_order), 0))\
        .filter(SubsidyRule.policy_id == policy_id).scalar() or 0
    r = SubsidyRule(
        policy_id=policy_id, rule_type=req.rule_type, rule_key=req.rule_key,
        rule_value=req.rule_value, rule_desc=req.rule_desc,
        source_quote=req.source_quote, sort_order=(req.sort_order if req.sort_order is not None else max_order + 1),
    )
    db.add(r)
    _reset_policy_ai_status(db, policy_id, current_user)
    db.commit()
    db.refresh(r)
    _log(db, current_user, "create", "subsidy_rule", r.id, after={"policy_id": policy_id, "rule_type": req.rule_type})
    return {"ok": True, "id": r.id}


@router.put("/policies/rules/{rule_id}")
def update_rule(rule_id: int, req: RuleEdit, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    """人工订正一条政策规则（改错、补全字段）。"""
    r = db.query(SubsidyRule).filter(SubsidyRule.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="规则不存在")
    for f in ("rule_type", "rule_key", "rule_value", "rule_desc", "source_quote", "sort_order"):
        v = getattr(req, f)
        if v is not None:
            setattr(r, f, v)
    _reset_policy_ai_status(db, r.policy_id, current_user)
    db.commit()
    _log(db, current_user, "update", "subsidy_rule", rule_id, after={"rule_type": r.rule_type, "rule_desc": r.rule_desc})
    return {"ok": True}


@router.delete("/policies/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db),
                current_user: SysUser = Depends(get_current_user)):
    """删除一条政策规则。"""
    r = db.query(SubsidyRule).filter(SubsidyRule.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="规则不存在")
    pid = r.policy_id
    db.delete(r)
    _reset_policy_ai_status(db, pid, current_user)
    db.commit()
    _log(db, current_user, "delete", "subsidy_rule", rule_id, after={"policy_id": pid})
    return {"ok": True}


@router.post("/policies/scan-folder")
def scan_policy_folder(
    force: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    """扫描 D:\\IP workflow\\人才补贴明细，按 folder_name 匹配政策，抽取文档并 AI 解析规则。"""
    if not POLICY_SCAN_ROOT.exists():
        raise HTTPException(status_code=400, detail=f"扫描目录不存在：{POLICY_SCAN_ROOT}")
    policies = db.query(SubsidyPolicy).filter(SubsidyPolicy.is_deleted == False).all()
    summary = []
    for policy in policies:
        folder = POLICY_SCAN_ROOT / (policy.folder_name or policy.policy_name)
        if not folder.exists():
            summary.append({"policy": policy.policy_name, "status": "no_folder", "detail": "本地无对应文件夹"})
            continue
        docs = [f for f in sorted(folder.iterdir())
                if f.is_file() and f.suffix.lower().lstrip(".") in DOC_EXT and not f.name.startswith("~$")]
        if not docs:
            summary.append({"policy": policy.policy_name, "status": "no_doc", "detail": "文件夹内无 PDF/Word"})
            continue
        doc = docs[0]
        # 抽取
        if not policy.raw_text or force:
            policy.raw_text = _extract_doc_text(str(doc))
        # 登记到文件中心（按路径去重）
        if not policy.source_file_id or force:
            exist = db.query(FileStorage).filter(
                FileStorage.business_type == "subsidy_policy",
                FileStorage.business_id == policy.id).first()
            if not exist:
                fext = doc.suffix.lower().lstrip(".")
                # 拷入 uploads/policy/ 并存相对路径，避免把本地绝对路径写进库
                copy_doc = POLICY_DOC_DIR / f"{uuid.uuid4().hex}_{doc.name}"
                shutil.copyfile(doc, copy_doc)
                fstore = FileStorage(
                    original_name=doc.name,
                    storage_path=str(copy_doc.relative_to(config.UPLOAD_DIR)).replace("\\", "/"),
                    file_type="word" if fext in ("doc", "docx") else "pdf",
                    file_size=copy_doc.stat().st_size, business_type="subsidy_policy",
                    business_id=policy.id, uploaded_by=current_user.id)
                db.add(fstore)
                db.flush()
                policy.source_file_id = fstore.id
        if not policy.raw_text or len(policy.raw_text.strip()) < 10:
            summary.append({"policy": policy.policy_name, "status": "empty_text", "detail": doc.name})
            continue
        if policy.ai_status == "parsed" and not force:
            summary.append({"policy": policy.policy_name, "status": "skipped", "detail": "已解析"})
            continue
        parsed = ai_bridge.parse_policy_rules(policy.raw_text)
        if not parsed.get("ok"):
            summary.append({"policy": policy.policy_name, "status": "parse_fail", "detail": parsed.get("error", "")[:120]})
            continue
        db.query(SubsidyRule).filter(SubsidyRule.policy_id == policy.id).delete()
        for r in _rules_from_json(policy, parsed["rules"]):
            db.add(r)
        policy.ai_status = "parsed"
        n = db.query(func.count(SubsidyRule.id)).filter(SubsidyRule.policy_id == policy.id).scalar() or 0
        summary.append({"policy": policy.policy_name, "status": "parsed", "detail": f"{doc.name} → {n} 条规则", "rule_count": n})
    db.commit()
    done = sum(1 for s in summary if s["status"] == "parsed")
    _log(db, current_user, "update", "subsidy_policy", 0,
         after={"scan_folder": done, "total": len(summary)})
    return {"ok": True, "scanned": len(summary), "parsed": done, "summary": summary}
