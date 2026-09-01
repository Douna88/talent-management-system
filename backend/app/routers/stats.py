"""统计路由：工作台关键指标 + 维度统计。"""
from collections import defaultdict
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    EmployeeTitle, TalentAccount, SubsidyPolicy, SubsidyApplication,
    SubsidyPayment, SysUser
)
from app.security import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    title_count = db.query(EmployeeTitle).filter(EmployeeTitle.is_deleted == False).count()
    account_count = db.query(TalentAccount).filter(TalentAccount.is_deleted == False).count()
    policy_count = db.query(SubsidyPolicy).filter(SubsidyPolicy.is_deleted == False).count()
    active_policy_count = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.status == "active").count()
    application_count = db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).count()
    payment_count = db.query(SubsidyPayment).count()
    pending_confirm = db.query(SubsidyPayment).filter(SubsidyPayment.status == "pending_confirm").count()
    total_paid = db.query(func.coalesce(func.sum(SubsidyPayment.amount), 0)).filter(
        SubsidyPayment.status == "paid").scalar() or 0
    confirmed_policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status == "confirmed").count()
    parsed_policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status == "parsed").count()
    pending_policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status == "pending").count()
    this_year = str(date.today().year)
    year_paid = db.query(func.coalesce(func.sum(SubsidyPayment.amount), 0)).filter(
        SubsidyPayment.status == "paid",
        SubsidyPayment.actual_date >= f"{this_year}-01-01").scalar() or 0

    return {
        "title_count": title_count,
        "account_count": account_count,
        "policy_count": policy_count,
        "active_policy_count": active_policy_count,
        "application_count": application_count,
        "payment_count": payment_count,
        "pending_confirm": pending_confirm,
        "total_paid": round(total_paid / 10000, 4),
        "confirmed_policy": confirmed_policy,
        "parsed_policy": parsed_policy,
        "pending_policy": pending_policy,
        "year": this_year,
        "year_paid": round(year_paid / 10000, 4),
    }


@router.get("/charts")
def charts(year: Optional[str] = Query(None, description="按发放年份筛选，传 'all' 或不传则看累计"),
           db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    """返回可视化图表所需的聚合数据；支持按年份筛选（仅影响分布类图表）。"""
    # 1. 年度发放趋势（按实际到账年份 sum，已发）——始终展示全量趋势；金额统一为万元
    year_trend = defaultdict(float)
    payments_all = db.query(SubsidyPayment).filter(SubsidyPayment.status.in_(("paid", "confirmed", "completed"))).all()
    for p in payments_all:
        y = p.actual_date.year if p.actual_date else (p.expected_date.year if p.expected_date else None)
        if y:
            year_trend[y] += (p.amount or 0) / 10000
    trend_years = sorted(year_trend.keys())
    trend = {"years": [str(y) for y in trend_years], "amounts": [round(year_trend[y], 4) for y in trend_years]}

    # 年份筛选：仅影响下面的分布类图表
    year_filter = None if (year in (None, "all", "")) else str(year)
    if year_filter:
        q = db.query(SubsidyPayment).filter(
            SubsidyPayment.status.in_(("paid", "confirmed", "completed")))
        rows = []
        for p in q.all():
            y = p.actual_date.year if p.actual_date else (p.expected_date.year if p.expected_date else None)
            if str(y) == year_filter:
                rows.append(p)
        policy_names = {p.id: p.policy_name for p in db.query(SubsidyPolicy).all()}
        policy_dist = defaultdict(float)
        bu_dist = defaultdict(float)
        person_dist = defaultdict(float)
        for p in rows:
            a = p.application
            if not a:
                continue
            amt = (p.amount or 0) / 10000
            pname = policy_names.get(a.policy_id, "未分类")
            policy_dist[pname] += amt
            bu_dist[a.bu or "未分配"] += amt
            person_dist[a.name] += amt
    else:
        # 累计：按申领 total_received（万元）
        policy_dist = defaultdict(float)
        policy_names = {p.id: p.policy_name for p in db.query(SubsidyPolicy).all()}
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            name = policy_names.get(a.policy_id, "未分类")
            policy_dist[name] += (a.total_received or 0) / 10000
        bu_dist = defaultdict(float)
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            bu = a.bu or "未分配"
            bu_dist[bu] += (a.total_received or 0) / 10000
        person_dist = defaultdict(float)
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            person_dist[a.name] += (a.total_received or 0) / 10000

    policy_pie = [{"name": k, "value": round(v, 4)} for k, v in sorted(policy_dist.items(), key=lambda x: -x[1])]
    bu_top = [{"name": k, "value": round(v, 4)} for k, v in sorted(bu_dist.items(), key=lambda x: -x[1])[:15]]
    person_top = [{"name": k, "value": round(v, 4)} for k, v in sorted(person_dist.items(), key=lambda x: -x[1])[:20]]

    # 5. 职称等级分布
    title_level_map = {
        "sub_senior": "高级工程师", "middle": "工程师", "junior": "助理工程师",
        "junior_researcher": "助理研究员", "level_1": "一级（高级技师）",
        "level_2": "二级（技师）", "level_3": "三级（高级工）"
    }
    title_dist = defaultdict(int)
    for t in db.query(EmployeeTitle).filter(EmployeeTitle.is_deleted == False).all():
        label = title_level_map.get(t.title_level, t.title_name or "其他")
        title_dist[label] += 1
    title_pie = [{"name": k, "value": v} for k, v in sorted(title_dist.items(), key=lambda x: -x[1])]

    # 6. 学历分布
    def _norm_edu(e):
        if not e:
            return "未知"
        e = e.strip()
        if e.upper() == "PHD":
            return "PhD"
        return e
    edu_dist = defaultdict(int)
    for t in db.query(EmployeeTitle).filter(EmployeeTitle.is_deleted == False).all():
        edu_dist[_norm_edu(t.education)] += 1
    edu_pie = [{"name": k, "value": v} for k, v in sorted(edu_dist.items(), key=lambda x: -x[1])]

    # 可选年份列表（供前端下拉）
    avail_years = [str(y) for y in trend_years]

    return {
        "year": year_filter or "all",
        "available_years": avail_years,
        "trend": trend,
        "policy_pie": policy_pie,
        "bu_top": bu_top,
        "person_top": person_top,
        "title_pie": title_pie,
        "edu_pie": edu_pie,
    }
