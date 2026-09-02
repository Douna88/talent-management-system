"""AI bridge: three-mode switch (none / local / cloud).

All AI calls go through this module so switching provider is a config change,
not a code change. The intranet LLM is OpenAI-compatible (no auth).

Capabilities:
  chat(messages, images)        -> {"ok", "content", "error"}   通用/多模态对话
  route_intent(question)        -> {"ok", "intent", "error"}    意图路由 query/action/chat
  nl2sql(question)              -> {"ok", "sql", "error"}       只读 SQL（强制中文别名）
  summarize(question, cols, rows) -> {"ok", "content", "error"} 结果 -> 自然语言（禁止 SQL）
  plan_action(question)         -> {"ok", "plan", "error"}      写操作计划（待人工确认）
  extract_file_text(path)       -> str                          附件文本抽取
"""
import base64
import json
import mimetypes
import re
import urllib.request
from pathlib import Path

from app import config


def is_enabled() -> bool:
    return config.AI_ENABLED and config.AI_PROVIDER in ("local", "cloud")


def provider() -> str:
    return config.AI_PROVIDER if is_enabled() else "none"


# ============================================================
# 底层调用
# ============================================================
def _chat_raw(messages: list, max_tokens: int = 2048, temperature: float = 0.3) -> str:
    """Call the OpenAI-compatible /chat/completions endpoint, return content text.

    messages[].content 可以是字符串，也可以是 OpenAI 多模态格式的分块列表：
      [{"type":"text","text":"..."},{"type":"image_url","image_url":{"url":"data:...;base64,..."}}]
    """
    url = f"{config.AI_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config.AI_API_KEY:
        headers["Authorization"] = f"Bearer {config.AI_API_KEY}"

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=config.AI_TIMEOUT)
        body = json.loads(resp.read().decode("utf-8"))
        msg = body["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        if not content:
            # 推理型模型在 max_tokens 过小时会把预算全用在思考上，导致返回空内容 —— 放宽预算重试一次
            payload["max_tokens"] = max(max_tokens * 4, 1024)
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            resp = urllib.request.urlopen(req, timeout=config.AI_TIMEOUT)
            body = json.loads(resp.read().decode("utf-8"))
            content = (body["choices"][0]["message"].get("content") or "").strip()
        return content
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"模型服务返回 HTTP {e.code}：{detail}")
    except Exception as e:
        raise RuntimeError(f"连接模型服务失败：{e}")


def _strip_code_fence(text: str) -> str:
    """去掉 ```json ... ``` 之类的代码块包裹。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        elif t.lower().startswith("sql"):
            t = t[3:]
    return t.strip()


def _json_from(text: str):
    """从模型输出中稳健地抠出第一个 JSON 对象。"""
    t = _strip_code_fence(text)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    frag = t[start:end + 1]
    try:
        return json.loads(frag)
    except json.JSONDecodeError:
        # 去掉尾部逗号等小问题再试一次
        frag2 = re.sub(r",\s*([}\]])", r"\1", frag)
        try:
            return json.loads(frag2)
        except json.JSONDecodeError:
            return None


def chat(messages: list, images: list = None, **kwargs) -> dict:
    """通用对话，可选附带图片（多模态）。

    images: [{"path": "..."} ] 或 [{"data_url": "data:image/png;base64,..."}]
    """
    if not is_enabled():
        return {"ok": False, "content": "", "error": "AI 未启用（请在配置中开启）"}

    msgs = [dict(m) for m in messages]
    if images and msgs:
        blocks = []
        for img in images:
            url = img.get("data_url")
            if not url and img.get("path"):
                url = image_to_data_url(img["path"])
            if url:
                blocks.append({"type": "image_url", "image_url": {"url": url}})
        last = msgs[-1]
        text = last.get("content", "") if isinstance(last.get("content"), str) else ""
        if blocks:
            blocks.append({"type": "text", "text": text})
            msgs[-1] = {"role": last.get("role", "user"), "content": blocks}
    try:
        content = _chat_raw(msgs, kwargs.get("max_tokens", 2048), kwargs.get("temperature", 0.3))
        return {"ok": True, "content": content, "error": ""}
    except Exception as e:
        return {"ok": False, "content": "", "error": str(e)}


def image_to_data_url(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


# ============================================================
# 意图路由：query(查数据) / action(改数据) / chat(聊天或咨询)
# ============================================================
INTENT_SYSTEM = (
    "你是人才补贴管理系统的助手路由。判断用户这句话属于哪一类，只输出 JSON，不要任何解释。\n"
    "可选 intent：\n"
    "  query  = 想【查】系统里已有的数据（多少人、多少钱、哪些人、什么时候、统计、排名、对比、导出清单）\n"
    "  action = 想【改】系统里的数据（新增、录入、添加、修改、更新、删除、改成、标注）\n"
    "  chat   = 其他：政策咨询、系统怎么用、概念解释、闲聊、对上传文件/图片提问\n"
    "输出格式：{\"intent\":\"query|action|chat\"}"
)


def route_intent(question: str) -> dict:
    if not is_enabled():
        return {"ok": False, "intent": "chat", "error": "AI 未启用"}
    try:
        content = _chat_raw(
            [{"role": "system", "content": INTENT_SYSTEM},
             {"role": "user", "content": question}],
            max_tokens=256, temperature=0.0,
        )
        obj = _json_from(content)
        intent = (obj or {}).get("intent", "chat")
        if intent not in ("query", "action", "chat"):
            intent = "chat"
        return {"ok": True, "intent": intent, "error": ""}
    except Exception as e:
        # 路由失败不阻塞，按聊天处理
        return {"ok": False, "intent": "chat", "error": str(e)}


# ============================================================
# 只读查询 NL2SQL
# ============================================================
DB_SCHEMA = """
数据库表（SQLite），金额单位统一为【元】，日期为 DATE 类型：

1) employee_title 职称（64 人左右）
   id, seq_no(序号), name(姓名), education(学历，取值：PhD/Master/Bachelor/Vocational College),
   title_name(职称类型), title_series(序列：engineering 工程类 / technician 技能类),
   title_level(等级), title_date(认定时间), major_field(专业), discipline(学科),
   next_stage_apply(下一阶段申请), remark(备注), is_deleted(0 有效 / 1 已删除)

2) talent_account 人才账号（146 人左右）
   id, name(姓名), digital_bank(数币银行), bank_name(普通开户行),
   has_subsidy(是否拿过补贴), remark(备注), is_deleted
   注意：具体账号号码是加密存储的，SQL 查不出来，只能查"有没有账号/哪家银行"。

3) subsidy_policy 补贴政策（16 个）
   id, policy_name(政策名), policy_category(类别), region(区域), region_level(级别),
   status(active/ended), is_deleted

4) subsidy_application 补贴申领（每人每政策一条，574 条左右）
   id, policy_id(关联 subsidy_policy.id), name(姓名),
   bu(BU，取值形如 BU1 / BU2 / BU3，一定以 BU 开头),
   department(部门，取值形如 机械部 / 电子部 / 测试部 / 软件部),
   hire_date(入职), awarded_date(获评), award_level(获评等级),
   total_expected(预计总额), total_received(累计到账),
   status(ongoing/completed/ended/stopped/resigned), remark(备注), is_deleted

5) subsidy_payment 发放明细（每期一条，990 条左右）
   id, application_id(关联 subsidy_application.id), payment_index(期次),
   expected_date(应发日期), actual_date(实发日期), amount(金额),
   status(pending/pending_confirm/confirmed/paid/stopped/unpaid/completed),
   conflict_flag(冲突标记), remark(备注)

6) payment_comment 批注
   id, payment_id(关联 subsidy_payment.id), author(批注人), content(批注内容), source(来源)

常用关联：
   subsidy_payment.application_id = subsidy_application.id
   subsidy_application.policy_id  = subsidy_policy.id
   payment_comment.payment_id     = subsidy_payment.id

按年份用 strftime('%Y', actual_date)；"已发放/已到账" 指 status 在 ('paid','confirmed','completed') 或 actual_date 非空。
"""

NL2SQL_PROMPT = (
    "你是 SQLite 查询生成器。根据表结构和用户问题，输出【一条只读 SELECT 语句】。\n"
    "严格规则：\n"
    "1. 只允许 SELECT 开头；禁止 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH/PRAGMA/REPLACE。\n"
    "2. 【每一列都必须用 AS 起简短中文别名】，例如：\n"
    "     SELECT name AS 姓名, SUM(amount) AS 发放总额 FROM ...\n"
    "     聚合列别名要体现业务含义：SUM(amount) AS 发放总额、COUNT(*) AS 人数、COUNT(DISTINCT name) AS 人数。\n"
    "3. 有效数据要过滤 is_deleted = 0（employee_title / talent_account / subsidy_application / subsidy_policy 有该字段）。\n"
    "4. 姓名模糊匹配一律写成 name LIKE '%张三%'；BU 用 bu = 'BU2-Glider' 精确匹配。\n"
    "5. 金额求和用 SUM，按年份用 strftime('%Y', actual_date) AS 年份。\n"
    "6. 分组用 GROUP BY，需要排名时 ORDER BY ... DESC LIMIT 20。\n"
    "7. 如果这个问题【不需要查数据库】（例如闲聊、政策咨询、系统用法），只输出单词：NO_SQL\n"
    "8. 只输出 SQL 本身或 NO_SQL，不要解释、不要 markdown 代码块、不要分号结尾以外的多余文字。\n\n"
    f"表结构：\n{DB_SCHEMA}\n\n"
    "用户问题：{question}\n"
    "SQL："
)


def nl2sql(question: str) -> dict:
    """把自然语言问题转成只读 SQL（带中文别名）。"""
    if not is_enabled():
        return {"ok": False, "sql": "", "error": "AI 未启用"}
    prompt = NL2SQL_PROMPT.replace("{question}", question)
    try:
        raw = _chat_raw(
            [{"role": "system", "content": "你是严谨的 SQLite 查询生成器，只输出一条只读 SELECT 语句。"},
             {"role": "user", "content": prompt}],
            max_tokens=1024, temperature=0.0,
        )
        sql = _strip_code_fence(raw).rstrip(";").strip()
        if sql.upper().startswith("NO_SQL"):
            return {"ok": True, "sql": "", "error": "", "no_sql": True}
        if not sql.lower().startswith("select"):
            return {"ok": False, "sql": "", "error": "模型生成了非查询语句，已拦截"}
        return {"ok": True, "sql": sql, "error": "", "no_sql": False}
    except Exception as e:
        return {"ok": False, "sql": "", "error": str(e)}


# ============================================================
# 列名友好化（避免把 COALESCE(SUM(x),0) 之类当表头显示）
# ============================================================
COL_LABELS = {
    "id": "ID", "seq_no": "序号", "name": "姓名", "gender": "性别",
    "education": "学历", "title_name": "职称", "title_series": "序列",
    "title_level": "等级", "title_date": "认定时间", "major_field": "专业",
    "discipline": "学科", "next_stage_apply": "下一阶段申请", "remark": "备注",
    "digital_bank": "数币银行", "bank_name": "开户行", "has_subsidy": "是否拿过补贴",
    "policy_id": "政策编号", "policy_name": "政策名称", "policy_category": "政策类别",
    "region": "区域", "region_level": "级别", "status": "状态",
    "bu": "BU", "department": "部门", "hire_date": "入职日期",
    "awarded_date": "获评日期", "award_level": "获评等级",
    "total_expected": "预计总额", "total_received": "累计到账",
    "application_id": "申领编号", "payment_index": "期次",
    "expected_date": "应发日期", "actual_date": "实发日期", "amount": "金额",
    "conflict_flag": "冲突标记", "payment_id": "发放编号",
    "author": "批注人", "content": "批注内容", "source": "来源",
}

_AGG_SUFFIX = {"sum": "合计", "count": "数量", "avg": "均值", "max": "最大", "min": "最小"}
_AGG_RE = re.compile(
    r"^\s*(?:coalesce\s*\(\s*)?(sum|count|avg|max|min)\s*\(\s*(?:distinct\s+)?([a-zA-Z_][\w.]*)\s*\)",
    re.I,
)


def friendly_columns(cols) -> list:
    out = []
    for c in cols:
        s = str(c)
        if re.search(r"[\u4e00-\u9fa5]", s):
            out.append(s)
            continue
        m = _AGG_RE.match(s)
        if m:
            fn, field = m.group(1).lower(), m.group(2).split(".")[-1]
            base = COL_LABELS.get(field, field)
            suffix = _AGG_SUFFIX.get(fn, "")
            if fn == "count" and field == "*":
                out.append("数量")
            else:
                out.append(f"{base}{suffix}" if suffix else base)
            continue
        out.append(COL_LABELS.get(s.strip(), s))
    return out


# ============================================================
# 结果 -> 自然语言（严禁出现 SQL）
# ============================================================
SUMMARIZE_SYSTEM = (
    "你是人才补贴管理系统的数据助手，负责把查询结果讲成人话。\n"
    "严格要求：\n"
    "1. 用自然、简洁的中文回答，直接给结论。\n"
    "2. 【绝对禁止】出现任何 SQL 关键字或代码片段，包括 SELECT / FROM / WHERE / GROUP BY / "
    "SUM() / COUNT() / COALESCE() / AS / 下划线字段名等。用户是非技术人员，看不懂也不该看到这些。\n"
    "3. 金额保留两位小数并带上「元」字，人数带「人」，笔数带「笔」。\n"
    "4. 结果超过 8 行时，先说总量/结论，再挑前几条列要点，不要逐行罗列。\n"
    "5. 如果结果为空，明确说明「没有查到相关数据」，并给出可能原因（如姓名写法不同、该年份无发放）。\n"
    "6. 不要编造数据，只依据给定的查询结果。"
)


def summarize(question: str, columns: list, rows: list, total: int) -> dict:
    if not is_enabled():
        return {"ok": False, "content": "", "error": "AI 未启用"}
    if not rows:
        return {"ok": True, "content": "没有查到相关数据。可能原因：姓名写法与系统不一致、该时间段尚无发放记录，或条件过严。可以换个说法再问我。", "error": ""}
    preview = rows[:30]
    payload = (
        f"用户问题：{question}\n"
        f"共 {total} 行结果，列名为：{columns}\n"
        f"数据（最多展示前 {len(preview)} 行）：\n{json.dumps(preview, ensure_ascii=False)}"
    )
    try:
        content = _chat_raw(
            [{"role": "system", "content": SUMMARIZE_SYSTEM},
             {"role": "user", "content": payload}],
            max_tokens=1024, temperature=0.2,
        )
        return {"ok": True, "content": content.strip(), "error": ""}
    except Exception as e:
        return {"ok": False, "content": "", "error": str(e)}


# ============================================================
# 写操作计划（生成后必须人工确认才执行）
# ============================================================
ACTION_SYSTEM = (
    "你是人才补贴管理系统的操作助手。用户想【修改系统数据】，你需要生成一个结构化的操作计划。\n"
    "只输出 JSON，不要任何解释，不要 markdown 代码块。\n\n"
    "可操作的实体与允许写入的字段：\n"
    "  talent_account 人才账号：name(姓名), digital_bank(数币银行), bank_name(开户行), has_subsidy(是否拿过补贴), remark(备注)\n"
    "  employee_title 职称：seq_no, name, education, title_name, title_series, title_level, title_date, major_field, discipline, next_stage_apply, remark\n"
    "  subsidy_policy 政策：policy_name, policy_category, region, region_level, status, remark\n"
    "  subsidy_application 申领：policy_id, name, bu, department, hire_date, awarded_date, award_level, total_expected, total_received, status, remark\n"
    "  subsidy_payment 发放：application_id, payment_index, expected_date, actual_date, amount, status, remark\n"
    "  payment_comment 批注：payment_id, author, content, source\n\n"
    "输出格式：\n"
    "{\n"
    '  "action": "create|update|delete",\n'
    '  "entity": "上表实体名之一",\n'
    '  "match": {"字段": "值"},        // update/delete 必填：定位目标记录的条件\n'
    '  "data": {"字段": "新值"},        // create/update 必填：要写入的字段\n'
    '  "explain": "一句话说明要做什么，给用户确认用"\n'
    "}\n\n"
    "规则：\n"
    "- 信息不足（比如不知道要改哪条记录）时，输出 {\"action\":\"clarify\",\"explain\":\"需要补充的信息\"}\n"
    "- 一次只做一个实体的一个操作；用户想批量做时，拆成最必要的那一条并说明。\n"
    "- 不要输出 SQL。"
)


def plan_action(question: str) -> dict:
    if not is_enabled():
        return {"ok": False, "plan": None, "error": "AI 未启用"}
    try:
        content = _chat_raw(
            [{"role": "system", "content": ACTION_SYSTEM},
             {"role": "user", "content": question}],
            max_tokens=1024, temperature=0.0,
        )
        obj = _json_from(content)
        if obj is None:
            return {"ok": False, "plan": None, "error": "模型没有返回可解析的操作计划"}
        return {"ok": True, "plan": obj, "error": ""}
    except Exception as e:
        return {"ok": False, "plan": None, "error": str(e)}


# ============================================================
# 系统知识问答（chat 意图）
# ============================================================
CHAT_SYSTEM = (
    "你是「人才补贴管理系统」的智能助手，服务对象是公司负责人才补贴的同事（非技术人员）。\n"
    "你能做的事：\n"
    "1. 回答系统里的人才、职称、补贴政策、发放记录相关问题；\n"
    "2. 解释补贴政策条款、申报条件、发放节奏；\n"
    "3. 说明系统各功能怎么用（职称管理、人才账号、补贴明细、统计图表、Excel 导入导出）；\n"
    "4. 就用户上传的图片、PDF、Word、Excel 文件内容进行解读和回答。\n"
    "回答要求：中文、口语化、结论先行、条目清晰；不确定的地方明确说「我不确定」，不要编造。"
)


def answer_chat(question: str, history: list = None, images: list = None,
                attachment_text: str = "") -> dict:
    msgs = [{"role": "system", "content": CHAT_SYSTEM}]
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": h["content"]})
    content = question
    if attachment_text:
        content = f"{question}\n\n【附件内容】\n{attachment_text[:12000]}"
    msgs.append({"role": "user", "content": content})
    return chat(msgs, images=images, max_tokens=2048, temperature=0.4)


# ============================================================
# 附件文本抽取
# ============================================================
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"}
TEXT_EXT = {"txt", "csv", "md", "json", "log"}


def classify_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext in IMAGE_EXT:
        return "image"
    if ext == "pdf":
        return "pdf"
    if ext in ("doc", "docx"):
        return "word"
    if ext in ("xls", "xlsx", "xlsm"):
        return "excel"
    if ext in ("ppt", "pptx"):
        return "ppt"
    return "other"


def extract_file_text(path: str, max_chars: int = 12000) -> str:
    """抽取附件文本；图片返回空串（图片走视觉通道）。"""
    p = Path(path)
    if not p.exists():
        return ""
    kind = classify_ext(p.name)
    try:
        if kind == "image":
            return ""
        if kind == "pdf":
            return _pdf_text(p, max_chars)
        if kind == "word":
            return _docx_text(p, max_chars)
        if kind == "excel":
            return _excel_text(p, max_chars)
        if kind == "ppt":
            return _ppt_text(p, max_chars)
        return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"（附件解析失败：{e}）"


def _pdf_text(p: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "（未安装 PDF 解析库，无法读取该 PDF 文本；可直接向我提问，或把内容复制过来）"
    try:
        reader = PdfReader(str(p))
        parts = []
        for i, page in enumerate(reader.pages[:40]):
            t = page.extract_text() or ""
            if t.strip():
                parts.append(f"— 第 {i + 1} 页 —\n{t.strip()}")
            if sum(len(x) for x in parts) > max_chars:
                break
        return "\n".join(parts)[:max_chars] or "（该 PDF 无可选文本层，可能是扫描件）"
    except Exception as e:
        return f"（PDF 解析失败：{e}）"


def _docx_text(p: Path, max_chars: int) -> str:
    try:
        import docx
    except ImportError:
        return "（未安装 Word 解析库，无法读取）"
    try:
        d = docx.Document(str(p))
        lines = [x.text.strip() for x in d.paragraphs if x.text.strip()]
        for tb in d.tables[:10]:
            for row in tb.rows:
                lines.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        return f"（Word 解析失败：{e}）"


def _excel_text(p: Path, max_chars: int) -> str:
    try:
        import openpyxl
    except ImportError:
        return "（未安装 Excel 解析库）"
    try:
        wb = openpyxl.load_workbook(str(p), data_only=True)
        out = []
        for ws in wb.worksheets[:5]:
            out.append(f"### 工作表：{ws.title}（{ws.max_row} 行）")
            for r in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 200), values_only=True):
                cells = ["" if v is None else str(v).strip() for v in r]
                if any(cells):
                    out.append(" | ".join(cells))
            if sum(len(x) for x in out) > max_chars:
                break
        return "\n".join(out)[:max_chars]
    except Exception as e:
        return f"（Excel 解析失败：{e}）"


def _ppt_text(p: Path, max_chars: int) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        return "（未安装 PPT 解析库）"
    try:
        prs = Presentation(str(p))
        lines = []
        for i, slide in enumerate(prs.slides):
            for shape in slide.shapes:
                if shape.has_text_frame:
                    t = shape.text_frame.text.strip()
                    if t:
                        lines.append(t)
            if sum(len(x) for x in lines) > max_chars:
                break
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        return f"（PPT 解析失败：{e}）"


# ============================================================
# 政策规则解析（保留原有能力）
# ============================================================
POLICY_RULES_SCHEMA = """
{
  "policy_name": "政策名称",
  "policy_category": "类别(薪酬补贴/紧缺人才/租房/房票/奖励/落户/乐居/就业创业/贡献/专项/安家/其他)",
  "region": "区域(苏州市/相城区/高铁新城等)",
  "region_level": "级别(市级/区级/县级)",
  "valid_from": "起始年份或日期，未知则null",
  "valid_until": "截止年份或日期，未知则null",
  "target_scope": "适用对象(应届生/紧缺人才/全部等)",
  "payment_schedule": {
    "total_amount": "总额(数字，未知0)",
    "installments": [
      {"index": 1, "amount": "第1笔金额", "trigger": "发放条件描述", "trigger_months": "需满月数或null"}
    ]
  },
  "eligibility": {
    "social_security_months": "需缴纳社保月数或null",
    "is_graduate_only": "是否仅应届生 true/false",
    "exclude_backfill_social_security": "补缴社保是否不算 true/false"
  },
  "conflict_rules": [
    {"conflict_with": "互斥政策名", "action": "择一/扣减/抵扣"}
  ],
  "special_notes": ["特殊条款列表"]
}
"""


def parse_policy_rules(text: str) -> dict:
    """把政策文档文本解析成结构化规则（AI，一次性、人审确认）。"""
    if not is_enabled():
        return {"ok": False, "rules": {}, "error": "AI 未启用，请先人工录入规则"}
    if not text or len(text.strip()) < 10:
        return {"ok": False, "rules": {}, "error": "政策文本为空或过短"}
    prompt = (
        "你是政策规则解析助手。请从下面的补贴政策文本中抽取发放规则，"
        "严格按 JSON 输出（只输出 JSON，不要任何解释、不要 markdown 代码块）：\n"
        f"JSON 结构要求：\n{POLICY_RULES_SCHEMA}\n\n"
        f"政策文本如下：\n{text[:12000]}"
    )
    try:
        content = _chat_raw(
            [{"role": "system", "content": "你是严谨的政策解析助手，只输出合法 JSON。"},
             {"role": "user", "content": prompt}],
            max_tokens=4096, temperature=0.1,
        )
        obj = _json_from(content)
        if obj is None:
            return {"ok": False, "rules": {}, "error": "模型未返回有效 JSON", "raw": content[:500]}
        return {"ok": True, "rules": obj, "error": ""}
    except Exception as e:
        return {"ok": False, "rules": {}, "error": str(e)}
