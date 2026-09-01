# -*- coding: utf-8 -*-
"""生成演示数据（全部为虚构数据，用于开源展示 / 本地体验）。

用法（在 backend 目录下执行）：
    python seed_demo.py

说明：
  1. 会清空现有业务数据后重建，请勿在存有真实数据的库上执行。
  2. 演示账号：admin / admin123
  3. 政策名称沿用各地公开发布的人才补贴政策（公开信息），
     人员姓名、金额、账号等均为随机生成的虚构数据。
"""
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base, SessionLocal, engine
from app.models import (
    SysUser, EmployeeTitle, TalentAccount, SubsidyPolicy, SubsidyRule,
    SubsidyApplication, SubsidyPayment, PaymentComment, AuditLog, FileStorage,
)
from app.security import hash_password
from app.encryption import encrypt_text, mask_account

random.seed(20260902)  # 固定种子，保证每次生成的演示数据一致

# ---------- 演示用姓名（虚构） ----------
SURNAMES = "张李王刘陈杨黄赵吴周徐孙马朱胡林郭何高罗郑梁谢宋唐许韩冯邓曹彭曾"
GIVEN = ["明", "静", "强", "洋", "磊", "娜", "涛", "敏", "超", "燕", "军", "洁",
         "伟", "芳", "勇", "玲", "辉", "霞", "斌", "婷", "杰", "颖", "峰", "琳"]

def fake_name():
    return random.choice(SURNAMES) + random.choice(GIVEN)

# ---------- 政策（各地公开发布的人才补贴政策，公开信息） ----------
POLICIES = [
    ("重点产业人才计划-薪酬补贴（2021-2023）", "薪酬补贴", "市辖区", "区级"),
    ("重点产业人才计划-薪酬补贴（2024-2026）", "薪酬补贴", "市辖区", "区级"),
    ("重点产业紧缺人才计划", "紧缺人才", "市辖区", "区级"),
    ("高端人才奖励计划", "奖励", "地级市", "市级"),
    ("人才乐居租房贴", "租房", "地级市", "市级"),
    ("优秀人才专项", "专项", "地级市", "市级"),
    ("重点产业紧缺人才计划（市级）", "紧缺人才", "地级市", "市级"),
    ("产业人才专项奖励", "奖励", "市辖区", "区级"),
    ("紧缺专技人才计划", "紧缺专技", "市辖区", "区级"),
    ("名校优生落户奖励", "落户", "市辖区", "区级"),
    ("人才贡献奖励", "贡献", "市辖区", "区级"),
    ("人才乐居补贴", "乐居", "市辖区", "区级"),
    ("重点产业人才计划-安家补贴", "安家", "市辖区", "区级"),
    ("应届高校毕业生租房补贴", "租房", "地级市", "市级"),
    ("重点产业人才计划-人才房票", "房票", "市辖区", "区级"),
    ("高技能人才培训补贴", "培训", "地级市", "市级"),
]

# 职称体系
TITLES_ENG = ["员级", "助理工程师", "工程师", "高级工程师", "正高级工程师"]
TITLES_TEC = ["三级（高级工）", "二级（技师）", "一级（高级技师）"]
EDUS = ["大专", "本科", "硕士", "博士"]
BUS = ["研发中心", "制造部", "质量部", "市场部", "供应链", "财务部", "人力资源部"]
BANKS = ["中国银行", "工商银行", "建设银行", "招商银行", "农业银行"]


def reset(db):
    """清空业务数据（按外键顺序删除）。"""
    for m in (PaymentComment, SubsidyPayment, SubsidyApplication, SubsidyRule,
              SubsidyPolicy, TalentAccount, EmployeeTitle, AuditLog, FileStorage):
        db.query(m).delete()
    db.query(SysUser).delete()
    db.commit()


def seed_users(db):
    db.add(SysUser(
        username="admin",
        password_hash=hash_password("admin123"),
        display_name="系统管理员",
        role="admin",
        status="active",
        created_at=datetime.now(),
    ))
    db.commit()


def seed_titles(db, n=30):
    """职称台账（虚构人员）。"""
    rows = []
    for i in range(1, n + 1):
        series = "engineering" if random.random() < 0.72 else "technician"
        level = random.choice(TITLES_ENG if series == "engineering" else TITLES_TEC)
        rows.append(EmployeeTitle(
            seq_no=i,
            name=fake_name(),
            education=random.choice(EDUS),
            title_name=level,
            title_series=series,
            title_level=level,
            title_date=date(2019 + random.randint(0, 6), random.randint(1, 12), random.randint(1, 28)),
            major_field=random.choice(["机械设计", "电气工程", "软件工程", "材料成型",
                                       "自动化", "光学工程", "工业工程", "化学工程"]),
            discipline=random.choice(["工学", "理学", "管理学"]),
            next_stage_apply=random.choice(["", "", "计划申报高一级职称", "材料准备中"]),
            is_deleted=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ))
    db.add_all(rows)
    db.commit()
    return [r.name for r in rows]


def seed_accounts(db, names, n=25):
    """人才账号（账号字段加密存储 + 列表脱敏展示）。"""
    rows = []
    for name in names[:n]:
        bank_account = "6222" + "".join(str(random.randint(0, 9)) for _ in range(15))
        digital_account = "0088" + "".join(str(random.randint(0, 9)) for _ in range(12))
        rows.append(TalentAccount(
            name=name,
            digital_bank=random.choice(BANKS),
            digital_account_encrypted=encrypt_text(digital_account),
            digital_account_mask=mask_account(digital_account),
            bank_name=random.choice(BANKS),
            bank_account_encrypted=encrypt_text(bank_account),
            bank_account_mask=mask_account(bank_account),
            has_subsidy=True,
            remark="演示数据",
            is_deleted=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ))
    db.add_all(rows)
    db.commit()


def seed_policies(db):
    rows = []
    for name, cat, region, level in POLICIES:
        rows.append(SubsidyPolicy(
            policy_name=name,
            policy_category=cat,
            region=region,
            region_level=level,
            folder_name=name,
            valid_from=date(2021, 1, 1),
            valid_until=date(2028, 12, 31),
            ai_status=random.choice(["confirmed", "confirmed", "parsed", "pending"]),
            status="active",
            remark="演示数据（政策原文为公开信息）",
            is_deleted=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ))
    db.add_all(rows)
    db.commit()
    return rows


def seed_rules(db, policies):
    """AI 解析出的政策规则（演示 AI 能力）。"""
    rule_tpl = [
        ("cycle", "发放周期", {"value": "按年发放"}, "补贴按年度分期发放"),
        ("amount", "补贴标准", {"value": "8000", "unit": "元/年"}, "每人每年 8000 元"),
        ("condition", "适用对象", {"value": "本科及以上学历，社保连续缴纳满 6 个月"}, "面向符合条件的在职人才"),
        ("duration", "享受期限", {"value": "3", "unit": "年"}, "最长享受 3 年"),
    ]
    rows = []
    for p in policies:
        if p.ai_status == "pending":
            continue
        for i, (rtype, key, value, desc) in enumerate(rule_tpl):
            rows.append(SubsidyRule(
                policy_id=p.id,
                rule_type=rtype,
                rule_key=key,
                rule_value=json.dumps(value, ensure_ascii=False),
                rule_desc=desc,
                source_quote=f"（演示）{p.policy_name} 相关规定摘录",
                sort_order=i,
                created_at=datetime.now(),
            ))
    db.add_all(rows)
    db.commit()


def seed_applications(db, policies, n=45):
    """补贴申领 + 分期发放记录。"""
    total_received_all = 0.0
    for i in range(n):
        policy = random.choice(policies)
        name = fake_name()
        bu = random.choice(BUS)
        awarded = date(2021 + random.randint(0, 4), random.randint(1, 12), random.randint(1, 28))
        periods = random.choice([1, 2, 3, 3, 4])
        per_amount = random.choice([8000, 12000, 15000, 20000, 30000, 50000])
        total_expected = per_amount * periods

        app = SubsidyApplication(
            policy_id=policy.id,
            name=name,
            bu=bu,
            department=bu,
            hire_date=awarded - timedelta(days=random.randint(200, 900)),
            awarded_date=awarded,
            award_level=random.choice(["", "市级", "区级", "重点"]),
            total_expected=total_expected,
            total_received=0,
            status="ongoing",
            is_deleted=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.add(app)
        db.flush()

        received = 0.0
        for k in range(1, periods + 1):
            expected = date(awarded.year + k - 1, awarded.month, min(awarded.day, 28))
            paid = expected <= date.today()
            st = "paid" if paid else "pending"
            p = SubsidyPayment(
                application_id=app.id,
                payment_index=k,
                expected_date=expected,
                actual_date=expected + timedelta(days=random.randint(0, 25)) if paid else None,
                amount=per_amount,
                status=st,
                remark="演示数据",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(p)
            db.flush()
            if paid:
                received += per_amount
                if random.random() < 0.18:  # 少量批注，展示协作留痕
                    db.add(PaymentComment(
                        payment_id=p.id,
                        author="demo.user",
                        content=random.choice([
                            "已与财务核对到账金额，无误。",
                            "本期发放延后，人社局拨款晚于预期。",
                            "员工社保缴纳月份已复核。",
                            "金额与政策标准一致。",
                        ]),
                        source="manual",
                        created_at=datetime.now(),
                    ))
        # 回写累计到账
        app.total_received = received
        if received >= total_expected:
            app.status = "completed"
        total_received_all += received

    db.commit()
    return total_received_all


def main():
    Base.metadata.create_all(bind=engine)
    db: SessionLocal = SessionLocal()
    try:
        print("清空既有数据 ...")
        reset(db)
        print("生成管理员账号 admin / admin123 ...")
        seed_users(db)
        print("生成职称台账 ...")
        names = seed_titles(db, 30)
        print("生成人才账号（加密存储）...")
        seed_accounts(db, names, 25)
        print("生成补贴政策与 AI 解析规则 ...")
        pols = seed_policies(db)
        seed_rules(db, pols)
        print("生成补贴申领与发放记录 ...")
        paid = seed_applications(db, pols, 45)

        # 统计
        from app.models import SubsidyApplication as SA, SubsidyPayment as SP
        print("\n=== 演示数据生成完成 ===")
        print(f"  职称记录      : {db.query(EmployeeTitle).count()} 条")
        print(f"  人才账号      : {db.query(TalentAccount).count()} 条（账号加密存储）")
        print(f"  补贴政策      : {db.query(SubsidyPolicy).count()} 项")
        print(f"  AI 解析规则   : {db.query(SubsidyRule).count()} 条")
        print(f"  补贴申领      : {db.query(SA).count()} 条")
        print(f"  发放记录      : {db.query(SP).count()} 笔")
        print(f"  发放批注      : {db.query(PaymentComment).count()} 条")
        print(f"  已发放合计    : {paid:,.0f} 元（{paid/10000:,.2f} 万元）")
        print("\n启动服务： python -m uvicorn app.main:app --port 8002")
        print("访问地址： http://localhost:8002   账号 admin / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
