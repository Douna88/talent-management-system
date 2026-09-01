"""汇报材料导出：PPT（公司模板）/ PDF / HTML。"""
import io
import json
from datetime import date
from typing import Optional
from urllib.parse import quote

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    EmployeeTitle, TalentAccount, SubsidyPolicy, SubsidyApplication,
    SubsidyPayment, SysUser, FileStorage, SubsidyRule,
)
from app.security import get_current_user

router = APIRouter(prefix="/api/export/report", tags=["report"])

PAGE_TITLE = "人才补贴管理汇报"
DEPT_NAME = "人力资源部"

# PPT 模板多候选（对齐 IP 系统 _find_template 方案）：
# ① 开发机 Downloads（本机）  ② backend/ 目录下随部署包携带（VM 用）
PPT_TEMPLATE_CANDIDATES = [
    str(Path(__file__).resolve().parent.parent.parent / "PPT模板.pptx"),
]


def _find_template():
    import os
    for p in PPT_TEMPLATE_CANDIDATES:
        if os.path.exists(p):
            return p
    return None

# 中文字体（用于 PDF 导出，reportlab 默认字体不支持中文）
import os as _os
_CN_FONT_PATHS = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\STXIHEI.TTF",
]
_CN_FONT_NAME = None


def _ensure_cn_font():
    """注册一个支持中文的 TTF 字体，返回字体名；找不到则报错。"""
    global _CN_FONT_NAME
    if _CN_FONT_NAME:
        return _CN_FONT_NAME
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for p in _CN_FONT_PATHS:
        if _os.path.exists(p):
            try:
                if p.lower().endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont("cn", p, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont("cn", p))
                _CN_FONT_NAME = "cn"
                return _CN_FONT_NAME
            except Exception:
                continue
    raise HTTPException(status_code=500, detail="未找到中文字体（simhei/msyh/simsun），无法生成中文 PDF")


# ============================================================
# 数据聚合
# ============================================================
def _gather(db: Session, year: str = None) -> dict:
    """聚合数据。year='all'/None 时口径为累计；否则按年度筛选（仅影响分布/年度指标）。"""
    from collections import defaultdict
    year_filter = None if (year in (None, "all", "")) else str(year)
    title_count = db.query(EmployeeTitle).filter(EmployeeTitle.is_deleted == False).count()
    account_count = db.query(TalentAccount).filter(TalentAccount.is_deleted == False).count()
    policy_count = db.query(SubsidyPolicy).filter(SubsidyPolicy.is_deleted == False).count()
    active_policy_count = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.status == "active").count()
    parsed_policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status == "confirmed").count()
    pending_policy = db.query(SubsidyPolicy).filter(
        SubsidyPolicy.is_deleted == False, SubsidyPolicy.ai_status.in_(("parsed", "pending"))).count()
    application_count = db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).count()
    payment_count = db.query(SubsidyPayment).count()
    pending_confirm = db.query(SubsidyPayment).filter(SubsidyPayment.status == "pending_confirm").count()
    total_paid = (db.query(func.coalesce(func.sum(SubsidyPayment.amount), 0)).filter(
        SubsidyPayment.status.in_(("paid", "confirmed", "completed"))).scalar() or 0) / 10000
    this_year = str(date.today().year)
    report_year = year_filter or this_year  # 报告所选年度（默认当前年）
    year_paid = (db.query(func.coalesce(func.sum(SubsidyPayment.amount), 0)).filter(
        SubsidyPayment.status.in_(("paid", "confirmed", "completed")),
        SubsidyPayment.actual_date >= f"{report_year}-01-01",
        SubsidyPayment.actual_date <= f"{report_year}-12-31").scalar() or 0) / 10000

    # 年度趋势（始终全量多年，万元）
    year_trend = defaultdict(float)
    for p in db.query(SubsidyPayment).filter(
            SubsidyPayment.status.in_(("paid", "confirmed", "completed"))).all():
        y = (p.actual_date or p.expected_date)
        if y:
            year_trend[y.year] += (p.amount or 0) / 10000
    years = sorted(year_trend.keys())
    trend = {"years": [str(y) for y in years],
             "amounts": [round(year_trend[y], 4) for y in years]}

    # 政策 / BU / 个人 分布（按所选年份筛选时，用 payment 聚合；累计时用 application.total_received）
    if year_filter:
        rows = []
        for p in db.query(SubsidyPayment).filter(
                SubsidyPayment.status.in_(("paid", "confirmed", "completed"))).all():
            y = p.actual_date.year if p.actual_date else (p.expected_date.year if p.expected_date else None)
            if str(y) == year_filter: rows.append(p)
        names = {pp.id: pp.policy_name for pp in db.query(SubsidyPolicy).all()}
        app_map = {a.id: a for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all()}
        policy_dist = defaultdict(float); bu_dist = defaultdict(float); person_dist = defaultdict(float)
        for p in rows:
            a = app_map.get(p.application_id)
            if not a: continue
            amt = (p.amount or 0) / 10000
            policy_dist[names.get(a.policy_id, "未分类")] += amt
            bu_dist[a.bu or "未分配"] += amt
            person_dist[a.name] += amt
    else:
        policy_dist = defaultdict(float)
        names = {p.id: p.policy_name for p in db.query(SubsidyPolicy).all()}
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            policy_dist[names.get(a.policy_id, "未分类")] += (a.total_received or 0) / 10000
        bu_dist = defaultdict(float)
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            bu_dist[a.bu or "未分配"] += (a.total_received or 0) / 10000
        person_dist = defaultdict(float)
        for a in db.query(SubsidyApplication).filter(SubsidyApplication.is_deleted == False).all():
            person_dist[a.name] += (a.total_received or 0) / 10000
    policy_pie = sorted([(k, round(v, 4)) for k, v in policy_dist.items()], key=lambda x: -x[1])
    bu_top = sorted([(k, round(v, 4)) for k, v in bu_dist.items()], key=lambda x: -x[1])[:10]
    person_top = sorted([(k, round(v, 4)) for k, v in person_dist.items()], key=lambda x: -x[1])[:10]

    return {
        "title_count": title_count, "account_count": account_count,
        "policy_count": policy_count, "active_policy_count": active_policy_count,
        "parsed_policy": parsed_policy, "pending_policy": pending_policy,
        "application_count": application_count, "payment_count": payment_count,
        "pending_confirm": pending_confirm,
        "total_paid": round(float(total_paid), 2),
        "year_paid": round(float(year_paid), 2),
        "year": report_year,
        "trend": trend, "policy_pie": policy_pie, "bu_top": bu_top, "person_top": person_top,
    }


# ============================================================
# PPT 导出（公司模板）
# ============================================================
@router.get("/ppt")
def export_ppt(year: Optional[str] = Query(None, description="按年度生成报告，'all'/不传=累计"),
               db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt

    tmpl = _find_template()
    if not tmpl:
        raise HTTPException(status_code=400, detail="未找到 PPT 模板，请将 PPT模板.pptx 放到 backend/ 目录后重试")
    data = _gather(db, year=year)
    prs = Presentation(tmpl)

    def fill(slide, title=None, subtitle=None, body_lines=None):
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            ph = sh.placeholder_format.type
            if ph == 1 and title is not None:
                sh.text_frame.text = title
            elif ph == 4 and subtitle is not None:
                sh.text_frame.text = subtitle
            elif ph == 2 and body_lines is not None:
                tf = sh.text_frame
                tf.clear()
                for i, line in enumerate(body_lines):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.text = line

    # 第 1 页：封面
    s0 = prs.slides[0]
    year_scope = "累计" if (year in (None, "all", "")) else f"{data['year']}年度"
    fill(s0, title=f"{PAGE_TITLE}（{year_scope}）",
         subtitle=f"{DEPT_NAME}　|　{date.today().strftime('%Y-%m-%d')}",
         body_lines=[f"{year_scope}已发放 {data['year_paid']:,.4f} 万元 · 累计发放 {data['total_paid']:,.4f} 万元 · 覆盖 {data['policy_count']} 项政策 · {data['application_count']} 条申领"])

    # 第 2 页：关键指标
    s1 = prs.slides[1]
    fill(s1, title=f"一、关键指标（{year_scope}）",
         body_lines=[
             f"· 职称人数：{data['title_count']} 人",
             f"· 人才账号：{data['account_count']} 个",
             f"· 补贴政策：{data['policy_count']} 项（在发 {data['active_policy_count']} 项，AI 已解析 {data['parsed_policy']} 项）",
             f"· 补贴申领：{data['application_count']} 条，发放笔数 {data['payment_count']} 笔",
             f"· 待确认发放：{data['pending_confirm']} 笔",
             f"· 累计已发放：{data['total_paid']:,.4f} 万元（{data['year']} 年已发放 {data['year_paid']:,.4f} 万元）",
         ])

    # 删除模板中多余的空白页（仅保留封面与关键指标两页），避免导出大量空白页
    _drop_extra_slides(prs, keep=2)

    # 其余页用模板空白布局追加图表 / 表格页
    try:
        layout = prs.slide_layouts[5]  # Title and Content
    except Exception:
        layout = prs.slide_layouts[1]

    def add_chart_slide(title, chart_type, categories, values, legend=True):
        slide = prs.slides.add_slide(layout)
        fill(slide, title=title)
        cd = CategoryChartData()
        cd.categories = categories
        cd.add_series("金额(万元)", values)
        gf = slide.shapes.add_chart(chart_type, Inches(0.8), Inches(1.6),
                                    Inches(8.6), Inches(4.6), cd)
        chart = gf.chart
        chart.has_legend = legend
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
        chart.has_title = False
        return slide

    # 政策累计到账 TOP（柱状）
    if data["policy_pie"]:
        top = data["policy_pie"][:10]
        add_chart_slide("二、各政策累计到账（TOP10）", XL_CHART_TYPE.COLUMN_CLUSTERED,
                        [n[:10] for n, _ in top], [v for _, v in top])
    # BU 分布（饼图）
    if data["bu_top"]:
        add_chart_slide("三、各 BU 累计到账占比", XL_CHART_TYPE.PIE,
                        [n for n, _ in data["bu_top"]], [v for _, v in data["bu_top"]])
    # 年度趋势（折线）
    if data["trend"]["years"]:
        add_chart_slide("四、年度发放趋势", XL_CHART_TYPE.LINE_MARKERS,
                        data["trend"]["years"], data["trend"]["amounts"], legend=False)
    # 个人 TOP（柱状）
    if data["person_top"]:
        add_chart_slide("五、个人累计到账（TOP10）", XL_CHART_TYPE.BAR_CLUSTERED,
                        [n[:10] for n, _ in data["person_top"]], [v for _, v in data["person_top"]])

    # 结语页
    end = prs.slides.add_slide(layout)
    fill(end, title="六、小结",
         body_lines=[
             f"系统已数字化沉淀 {data['policy_count']} 项政策、{data['application_count']} 条申领，累计发放 {data['total_paid']:,.4f} 万元。",
             f"AI 已解析 {data['parsed_policy']} 项政策规则，发放确认流程线上化、可追溯。",
             "下一步：补全剩余政策 AI 解析与规则确认，并接入集团人才数据。",
         ])

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    fn = f"人才补贴管理汇报_{data['year']}.pptx"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fn)}"}
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", headers=headers)


def _drop_extra_slides(prs, keep: int = 2):
    """删除模板中多余的空白页（保留前 keep 页），避免导出大量空白页。
    同时清理未被引用的 slide part 及其关系，防止 PowerPoint 弹出内容修复提示。"""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    KEEP_RT = {RT.SLIDE_LAYOUT, RT.SLIDE_MASTER, RT.THEME, RT.NOTES_SLIDE}
    sldIdLst = prs.slides._sldIdLst
    slides = list(sldIdLst)
    dropped_rids = [sld.get("{%s}id" % sldIdLst.nsmap["r"]) for sld in slides[keep:]]
    for sld in slides[keep:]:
        sldIdLst.remove(sld)
    main_part = prs.part
    for rid in dropped_rids:
        try:
            target_part = main_part.related_part(rid)
        except KeyError:
            continue
        for rel in list(target_part.rels.values()):
            if rel.reltype in KEEP_RT:
                continue
            try:
                target_part.drop_rel(rel.rId)
            except Exception:
                pass
        try:
            main_part.package.drop_part(target_part.partname)
        except Exception:
            pass
        try:
            main_part.drop_rel(rid)
        except KeyError:
            pass


# ============================================================
# HTML 导出
# ============================================================
def _fmt(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return str(v)


@router.get("/html", response_class=HTMLResponse)
def export_html(year: Optional[str] = Query(None, description="按年度生成报告，'all'/不传=累计"),
                db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    d = _gather(db, year=year)
    pct = lambda v, tot: (100 * v / tot) if tot else 0
    tot = d["total_paid"] or 1

    def bar_table(rows, unit="元"):
        out = []
        for name, val in rows:
            w = max(2, int(pct(val, tot) * 100))
            out.append(
                f"<tr><td class='name'>{name}</td><td class='num'>{_fmt(val)}</td>"
                f"<td class='barcell'><div class='bar' style='width:{w}%'></div></td></tr>")
        return "\n".join(out)

    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>{PAGE_TITLE}（{d['year']}年度）</title>
<style>
 body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;margin:0;background:#f5f6f8;color:#222}}
 .wrap{{max-width:920px;margin:24px auto;background:#fff;padding:32px 28px;box-shadow:0 2px 8px rgba(0,0,0,.08);overflow-x:auto}}
 h1{{color:#c0392b;border-bottom:3px solid #c0392b;padding-bottom:8px}}
 h2{{color:#1f2d3d;margin-top:28px;border-left:4px solid #c0392b;padding-left:10px}}
 .cards{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}
 .card{{flex:1;min-width:150px;background:#fafafa;border:1px solid #eee;border-radius:8px;padding:14px}}
 .card .v{{font-size:24px;font-weight:700;color:#c0392b}}
 .card .l{{font-size:13px;color:#888}}
 table{{width:100%;border-collapse:collapse;margin:10px 0;table-layout:fixed}}
 td,th{{border:1px solid #eee;padding:6px 10px;font-size:14px;word-break:break-all}}
 th{{background:#f0f2f5}}
 .name{{width:auto;overflow:hidden;text-overflow:ellipsis}}
 .num{{width:130px;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
 .barcell{{width:50%;overflow:hidden}}
 .bar{{height:14px;max-width:100%;background:linear-gradient(90deg,#c0392b,#e67e22);border-radius:7px}}
 .foot{{color:#aaa;font-size:12px;margin-top:30px;text-align:center}}
</style></head><body><div class="wrap">
<h1>{PAGE_TITLE}（{d['year']}年度）</h1>
<p>{DEPT_NAME}　|　{date.today().strftime('%Y-%m-%d')}　|　口径：{d['year']}年度</p>
<div class="cards">
 <div class="card"><div class="v">{d['title_count']}</div><div class="l">职称人数</div></div>
 <div class="card"><div class="v">{d['account_count']}</div><div class="l">人才账号</div></div>
 <div class="card"><div class="v">{d['policy_count']}</div><div class="l">补贴政策</div></div>
 <div class="card"><div class="v">{d['application_count']}</div><div class="l">补贴申领</div></div>
 <div class="card"><div class="v">{_fmt(d['total_paid'])}</div><div class="l">累计已发(万元)</div></div>
</div>
<h2>各政策累计到账</h2>
<table><tr><th class="name">政策</th><th class="num">金额(万元)</th><th class="barcell">占比</th></tr>
{bar_table(d['policy_pie'][:15])}
</table>
<h2>各 BU 累计到账</h2>
<table><tr><th class="name">BU</th><th class="num">金额(万元)</th><th class="barcell">占比</th></tr>
{bar_table(d['bu_top'])}
</table>
<h2>个人累计到账 TOP10</h2>
<table><tr><th class="name">姓名</th><th class="num">金额(万元)</th><th class="barcell">占比</th></tr>
{bar_table(d['person_top'])}
</table>
<h2>年度发放趋势</h2>
<table><tr><th>年份</th><th>金额(万元)</th></tr>
{''.join(f"<tr><td>{y}</td><td class='num'>{_fmt(a)}</td></tr>" for y,a in zip(d['trend']['years'], d['trend']['amounts']))}
</table>
<div class="foot">由人才补贴管理系统自动生成 · {date.today().strftime('%Y-%m-%d %H:%M')}</div>
</div></body></html>"""
    fn = "人才补贴管理汇报_" + d["year"] + ".html"
    return HTMLResponse(content=html, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(fn)}"})


# ============================================================
# PDF 导出（reportlab）
# ============================================================
@router.get("/pdf")
def export_pdf(year: Optional[str] = Query(None, description="按年度生成报告，'all'/不传=累计"),
               db: Session = Depends(get_db), current_user: SysUser = Depends(get_current_user)):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                        TableStyle, PageBreak)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.graphics.shapes import Drawing
        from reportlab.graphics.charts.barcharts import HorizontalBarChart
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics.charts.legends import Legend
        from reportlab.graphics.widgets.markers import makeMarker
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF 库未安装（reportlab）")

    d = _gather(db, year=year)
    cn = _ensure_cn_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.4 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            title=PAGE_TITLE)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName=cn, fontSize=20, textColor=colors.HexColor("#c0392b"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=cn, fontSize=14, textColor=colors.HexColor("#1f2d3d"))
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName=cn, fontSize=10)
    elems = [
        Paragraph(f"{PAGE_TITLE}（{d['year']}年度）", h1),
        Paragraph(f"{DEPT_NAME}　|　{date.today().strftime('%Y-%m-%d')}　|　口径：{d['year']}年度", body),
        Spacer(1, 0.3 * cm),
    ]

    cards = [["职称人数", "人才账号", "补贴政策", "补贴申领", "累计已发(万元)"],
             [str(d["title_count"]), str(d["account_count"]), str(d["policy_count"]),
              str(d["application_count"]), f"{d['total_paid']:,.4f}"]]
    t = Table(cards, colWidths=[3.4 * cm] * 5)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#888888")),
        ("FONTNAME", (0, 0), (-1, -1), cn),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("FONTNAME", (0, 1), (-1, 1), cn),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#c0392b")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#eeeeee")),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems += [t, Spacer(1, 0.4 * cm)]

    def bar_drawing(rows, w=16 * cm, title=""):
        h = max(0.42 * cm * len(rows), 1.5 * cm)
        d_w = Drawing(w, h)
        bc = HorizontalBarChart()
        bc.x = 5 * cm
        bc.y = 0.2 * cm
        bc.height = max(h - 0.4 * cm, 1.2 * cm)
        bc.width = w - 5.2 * cm
        bc.data = [[v for _, v in rows]]
        bc.categoryAxis.categoryNames = [n[:12] for n, _ in rows]
        bc.bars[0].fillColor = colors.HexColor("#c0392b")
        bc.valueAxis.valueMin = 0
        bc.categoryAxis.labels.fontName = cn
        bc.valueAxis.labels.fontName = cn
        bc.categoryAxis.labels.fontSize = 8
        bc.valueAxis.labels.fontSize = 7
        d_w.add(bc)
        return d_w

    if d["policy_pie"]:
        elems += [Paragraph("各政策累计到账（TOP10）", h2),
                  bar_drawing(d["policy_pie"][:10]), Spacer(1, 0.3 * cm)]
    if d["bu_top"]:
        elems += [Paragraph("各 BU 累计到账", h2),
                  bar_drawing(d["bu_top"]), Spacer(1, 0.3 * cm)]

    # 个人 TOP10 表格
    if d["person_top"]:
        elems += [Paragraph("个人累计到账 TOP10", h2)]
        rows = [["姓名", "金额(万元)"]] + [[n, f"{v:,.4f}"] for n, v in d["person_top"]]
        pt = Table(rows, colWidths=[8 * cm, 8 * cm])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f5")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#eeeeee")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), cn),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        elems += [pt, PageBreak()]

    # 年度趋势表
    elems += [Paragraph("年度发放趋势", h2)]
    rows = [["年份", "金额(万元)"]] + [[y, f"{a:,.4f}"] for y, a in zip(d["trend"]["years"], d["trend"]["amounts"])]
    yt = Table(rows, colWidths=[8 * cm, 8 * cm])
    yt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f2f5")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#eeeeee")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), cn),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elems += [yt]

    doc.build(elems)
    buf.seek(0)
    fn = "人才补贴管理汇报_" + d["year"] + ".pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(fn)}"})
