"""AI 路由 v2.4

设计原则：
1. 用户永远看不到 SQL —— 只看到自然语言回答 + 结果表格（列名已中文化）。
2. 意图路由：query(查数据) / action(改数据) / chat(咨询&多模态)。
3. 写操作必须先生成计划 → 前端确认 → 再执行（白名单字段 + 审计日志）。
4. 多模态：图片走模型视觉通道，PDF/Word/Excel/PPT 抽取文本后一起提问。

接口：
  POST /api/ai/chat      多模态统一入口（Form: question, history, files[]）
  POST /api/ai/query     纯文本查询（JSON: {question}）—— 兼容旧前端
  POST /api/ai/action    执行已确认的写操作计划
  POST /api/ai/parse-policy  政策文本 -> 结构化规则
  GET  /api/ai/status    AI 连接状态
"""
import json
import re
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app import ai_bridge, config
from app.database import get_db
from app.models import (
    AuditLog, EmployeeTitle, FileStorage, PaymentComment, SubsidyApplication,
    SubsidyPayment, SubsidyPolicy, SysUser, TalentAccount,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])

AI_UPLOAD_DIR = config.UPLOAD_DIR / "ai"
AI_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class QueryRequest(BaseModel):
    question: str
    history: Optional[list] = None


class ParsePolicyRequest(BaseModel):
    text: str


class ActionRequest(BaseModel):
    plan: dict


# ============================================================
# SQL 安全审计（只读通道）
# ============================================================
FORBIDDEN = ("insert", "update", "delete", "drop", "alter", "create",
             "truncate", "grant", "revoke", "attach", "detach", "replace",
             "pragma", "exec", "load")


def _safe_sql(sql: str) -> str:
    s = sql.strip().rstrip(";").strip()
    low = s.lower()
    if not low.startswith("select"):
        raise HTTPException(status_code=400, detail="只允许查询类语句")
    for kw in FORBIDDEN:
        if re.search(rf"\b{kw}\b", low):
            raise HTTPException(status_code=400, detail="该查询包含不被允许的操作，已拦截")
    if s.count(";") > 0:
        raise HTTPException(status_code=400, detail="不接受多条语句")
    return s


def _rows_to_dicts(rows, limit: int = 200):
    data = []
    for r in rows[:limit]:
        d = dict(r._mapping)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
            elif isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
        data.append(d)
    return data


def _run_query(db: Session, question: str) -> dict:
    """NL2SQL -> 执行 -> 自然语言回答 + 友好列名结果表（不返回 SQL）。"""
    res = ai_bridge.nl2sql(question)
    if not res.get("ok"):
        return {"ok": False, "mode": "query", "answer": None,
                "message": res.get("error") or "没能理解这个问题，换个说法试试？"}
    if res.get("no_sql") or not res.get("sql"):
        return {"ok": False, "mode": "query", "answer": None,
                "message": None, "fallback_chat": True}

    sql = res["sql"]
    try:
        rows = db.execute(text(_safe_sql(sql))).fetchall()
    except HTTPException:
        raise
    except Exception as e:
        # 不外抛 SQL，只给友好提示；并降级为聊天回答
        return {"ok": False, "mode": "query", "answer": None,
                "message": "这次查询没能跑通，我已经改用通用方式回答。", "fallback_chat": True}

    total = len(rows)
    columns = list(rows[0]._mapping.keys()) if rows else []
    data = _rows_to_dicts(rows)
    friendly = ai_bridge.friendly_columns(columns)

    # 把 data 的 key 换成友好列名，前端表格表头即为中文
    renamed = []
    mapping = {str(c): f for c, f in zip(columns, friendly)}
    for d in data:
        renamed.append({mapping.get(k, k): v for k, v in d.items()})

    ans = ai_bridge.summarize(question, friendly, data, total)
    answer = ans.get("content") if ans.get("ok") else (
        f"查到了 {total} 条结果。" if total else "没有查到相关数据。")
    if ans.get("ok") is False and total:
        answer = f"查到了 {total} 条结果（自动解读未成功，先看表格）。"

    return {"ok": True, "mode": "query", "answer": answer,
            "rows": renamed, "columns": friendly, "total": total}


def _run_chat(question: str, history: list = None,
              images: list = None, attachment_text: str = "") -> dict:
    res = ai_bridge.answer_chat(question, history=history, images=images,
                                attachment_text=attachment_text)
    if not res.get("ok"):
        return {"ok": False, "mode": "chat", "answer": None, "message": res.get("error")}
    return {"ok": True, "mode": "chat", "answer": res.get("content")}


def _route(question: str, db: Session, history: list = None,
           images: list = None, attachment_text: str = "") -> dict:
    """按意图分派。"""
    if not ai_bridge.is_enabled():
        return {"ok": False, "mode": "chat", "answer": None,
                "message": "AI 未开启，请联系管理员在配置中启用。"}

    # 有附件时优先走多模态/文本解读通道
    if images or attachment_text:
        return _run_chat(question, history, images, attachment_text)

    intent_res = ai_bridge.route_intent(question)
    intent = intent_res.get("intent", "chat")

    if intent == "action":
        plan_res = ai_bridge.plan_action(question)
        if plan_res.get("ok") and isinstance(plan_res.get("plan"), dict):
            plan = plan_res["plan"]
            if plan.get("action") == "clarify":
                return {"ok": True, "mode": "chat",
                        "answer": f"我可以帮你改，但还差一点信息：{plan.get('explain', '请补充说明要改哪条记录、改成什么')}"}
            return {"ok": True, "mode": "action", "plan": plan,
                    "answer": plan.get("explain") or "我准备进行如下操作，请确认：",
                    "need_confirm": True}
        return {"ok": False, "mode": "chat", "answer": None,
                "message": plan_res.get("error") or "没能生成操作方案，请说得更具体一点。"}

    # 兜底：即使路由判成 chat，只要问题里带明显的"查数"词，也先试一次查库，
    # 避免模型偶尔误判导致"明明系统里有数据却说查不到"。
    QUERY_HINT = ("多少", "几个", "哪些", "谁", "统计", "汇总", "排名", "排行",
                  "总额", "人数", "笔数", "清单", "列表", "明细", "合计",
                  "有没有", "多少次", "对比", "平均", "最高", "最多", "总额")
    looks_like_query = any(k in question for k in QUERY_HINT)

    if intent == "query" or looks_like_query:
        q = _run_query(db, question)
        if q.get("ok"):
            return q
        if q.get("fallback_chat"):
            return _run_chat(question, history, images, attachment_text)
        return q

    return _run_chat(question, history, images, attachment_text)


# ============================================================
# 统一多模态入口
# ============================================================
@router.post("/chat")
async def ai_chat(
    question: str = Form(""),
    history: str = Form("[]"),
    files: List[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    try:
        hist = json.loads(history or "[]")
    except json.JSONDecodeError:
        hist = []

    image_paths, texts = [], []
    for f in (files or []):
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower().lstrip(".")
        if ext not in config.ALLOWED_EXTENSIONS:
            continue
        saved = AI_UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
        with saved.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        size = saved.stat().st_size
        db.add(FileStorage(
            original_name=f.filename,
            storage_path=str(saved.relative_to(config.UPLOAD_DIR)).replace("\\", "/"),
            file_type=ai_bridge.classify_ext(f.filename), file_size=size,
            mime_type=f.content_type, business_type="ai_chat",
            uploaded_by=current_user.id,
        ))
        kind = ai_bridge.classify_ext(f.filename)
        if kind == "image":
            image_paths.append(str(saved))
        else:
            t = ai_bridge.extract_file_text(str(saved))
            if t:
                texts.append(f"【附件：{f.filename}】\n{t}")
    db.commit()

    q = (question or "").strip()
    if not q and texts:
        q = "请帮我解读并总结这些附件中与人才补贴相关的内容。"
    if not q and image_paths:
        q = "请识别并说明这张图片的内容。"

    result = _route(q, db, hist, images=[{"path": p} for p in image_paths],
                    attachment_text="\n\n".join(texts))
    result["provider"] = ai_bridge.provider()
    return result


# ============================================================
# 纯文本查询（兼容旧调用）
# ============================================================
@router.post("/query")
def ai_query(req: QueryRequest, db: Session = Depends(get_db),
             current_user: SysUser = Depends(get_current_user)):
    q = (req.question or "").strip()
    if not q:
        return {"ok": False, "mode": "chat", "answer": None, "message": "请输入问题"}
    result = _route(q, db, req.history or [])
    result["provider"] = ai_bridge.provider()
    return result


# ============================================================
# 写操作：白名单 + 审计
# ============================================================
ENTITY_MAP = {
    "talent_account": (TalentAccount, {
        "name", "digital_bank", "bank_name", "has_subsidy", "remark"}),
    "employee_title": (EmployeeTitle, {
        "seq_no", "name", "education", "title_name", "title_series",
        "title_level", "title_date", "major_field", "discipline",
        "next_stage_apply", "remark"}),
    "subsidy_policy": (SubsidyPolicy, {
        "policy_name", "policy_category", "region", "region_level", "status", "remark"}),
    "subsidy_application": (SubsidyApplication, {
        "policy_id", "name", "bu", "department", "hire_date", "awarded_date",
        "award_level", "total_expected", "total_received", "status", "remark"}),
    "subsidy_payment": (SubsidyPayment, {
        "application_id", "payment_index", "expected_date", "actual_date",
        "amount", "status", "remark"}),
    "payment_comment": (PaymentComment, {
        "payment_id", "author", "content", "source"}),
}

DATE_FIELDS = {"title_date", "hire_date", "awarded_date", "expected_date", "actual_date"}
NUM_FIELDS = {"seq_no", "policy_id", "application_id", "payment_id",
              "payment_index", "total_expected", "total_received", "amount", "id"}


def _coerce(field: str, value):
    if value is None:
        return None
    if field in DATE_FIELDS:
        if isinstance(value, date):
            return value
        s = str(value).strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y-%m", "%Y/%m", "%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
    if field in NUM_FIELDS:
        try:
            f = float(value)
            return int(f) if f.is_integer() else f
        except (TypeError, ValueError):
            return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return value


def _log(db: Session, user: SysUser, action: str, entity: str,
         before, after, business_id=None):
    db.add(AuditLog(
        user_id=user.id, user_name=user.display_name or user.username,
        action=action, business_type=f"ai_{entity}", business_id=business_id,
        before_value=json.dumps(before, ensure_ascii=False, default=str) if before else None,
        after_value=json.dumps(after, ensure_ascii=False, default=str) if after else None,
    ))


def _snapshot(obj, fields):
    out = {}
    for f in fields:
        v = getattr(obj, f, None)
        out[f] = v.isoformat() if isinstance(v, (date, datetime)) else v
    return out


DONE_STATUSES = ("paid", "confirmed", "completed")


def _recalc_application_total(db: Session, app_id):
    """发放明细变动后，同步重算所属申领的"累计到账"。"""
    if not app_id:
        return
    app = db.query(SubsidyApplication).filter(SubsidyApplication.id == app_id).first()
    if not app:
        return
    total = db.query(func.coalesce(func.sum(SubsidyPayment.amount), 0.0)).filter(
        SubsidyPayment.application_id == app_id,
        SubsidyPayment.status.in_(DONE_STATUSES),
    ).scalar()
    app.total_received = round(float(total or 0), 2)


@router.post("/action")
def ai_action(req: ActionRequest, db: Session = Depends(get_db),
              current_user: SysUser = Depends(get_current_user)):
    """执行已确认的写操作计划（字段白名单 + 审计日志）。"""
    plan = req.plan or {}
    entity = plan.get("entity")
    action = plan.get("action")
    data = plan.get("data") or {}
    match = plan.get("match") or {}

    if entity not in ENTITY_MAP:
        raise HTTPException(status_code=400, detail=f"不支持的数据对象：{entity}")
    model, allowed = ENTITY_MAP[entity]

    data = {k: v for k, v in data.items() if k in allowed and k != "id"}
    match = {k: v for k, v in match.items() if k in allowed or k == "id"}
    if not data and action in ("create", "update"):
        raise HTTPException(status_code=400, detail="没有可写入的字段，操作已取消")

    try:
        if action == "create":
            obj = model(**{k: _coerce(k, v) for k, v in data.items()})
            if hasattr(model, "created_by"):
                obj.created_by = current_user.id
            db.add(obj)
            db.flush()
            _log(db, current_user, "create", entity, None, _snapshot(obj, data.keys()), obj.id)
            if entity == "subsidy_payment":
                _recalc_application_total(db, getattr(obj, "application_id", None))
            db.commit()
            return {"ok": True, "action": "create", "entity": entity, "id": obj.id,
                    "answer": f"已新增一条{entity}记录（编号 {obj.id}）。"}

        if action in ("update", "delete"):
            if not match:
                raise HTTPException(status_code=400, detail="缺少定位条件，不知道要改哪条记录")
            q = db.query(model)
            for k, v in match.items():
                q = q.filter(getattr(model, k) == _coerce(k, v))
            if hasattr(model, "is_deleted"):
                q = q.filter(model.is_deleted == False)  # noqa: E712
            targets = q.limit(50).all()
            if not targets:
                db.rollback()
                return {"ok": False, "action": action, "entity": entity,
                        "answer": "没有找到匹配的记录，操作未执行。"}
            if len(targets) > 1 and action == "delete":
                return {"ok": False, "action": action, "entity": entity,
                        "answer": f"匹配到 {len(targets)} 条记录，删除风险较高，请到对应页面手动处理，或把条件说得更精确。"}

            affected = []
            touched_apps = set()
            for obj in targets:
                before = _snapshot(obj, set(data.keys()) | set(match.keys()))
                if entity == "subsidy_payment":
                    touched_apps.add(getattr(obj, "application_id", None))
                if action == "update":
                    for k, v in data.items():
                        setattr(obj, k, _coerce(k, v))
                    after = _snapshot(obj, data.keys())
                else:
                    if hasattr(obj, "is_deleted"):
                        obj.is_deleted = True
                        after = {"is_deleted": True}
                    else:
                        db.delete(obj)
                        after = None
                _log(db, current_user, action, entity, before, after, obj.id)
                affected.append(obj.id)
            for app_id in touched_apps:
                _recalc_application_total(db, app_id)
            db.commit()
            verb = "更新" if action == "update" else "删除"
            return {"ok": True, "action": action, "entity": entity, "ids": affected,
                    "count": len(affected), "answer": f"已{verb} {len(affected)} 条记录。"}

        raise HTTPException(status_code=400, detail=f"不支持的操作：{action}")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"操作失败：{e}")


# ============================================================
# 政策解析 / 状态
# ============================================================
@router.post("/parse-policy")
def parse_policy(req: ParsePolicyRequest,
                 current_user: SysUser = Depends(get_current_user)):
    return ai_bridge.parse_policy_rules(req.text)


@router.get("/status")
def ai_status():
    return {
        "enabled": ai_bridge.is_enabled(),
        "provider": ai_bridge.provider(),
        "model": config.AI_MODEL,
        "vision": True,
        "can_write": True,
    }
