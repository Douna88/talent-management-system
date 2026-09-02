"""SQLAlchemy models for the talent management system (independent system).

Tables: sys_user, employee, file_storage, audit_log, reminder (infrastructure)
        employee_title, title_certificate (职称)
        talent_account (人才账号)
        subsidy_policy, subsidy_rule, subsidy_application, subsidy_payment,
        payment_comment, subsidy_conflict (补贴)
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    Float, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


# ===== infrastructure =====
class SysUser(Base):
    __tablename__ = "sys_user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(50), nullable=False)
    email = Column(String(100))
    role = Column(String(20), nullable=False, default="admin")  # admin/member/viewer
    status = Column(String(10), nullable=False, default="active")  # active/disabled
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)


class Employee(Base):
    __tablename__ = "employee"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, index=True)
    department = Column(String(100))
    bu = Column(String(50))
    hire_date = Column(Date)
    email = Column(String(100))
    phone = Column(String(20))
    status = Column(String(10), default="active")  # active/resigned
    is_researcher = Column(Boolean, default=False)  # 是否研发人员
    has_subsidy = Column(Boolean, default=False)     # 是否拿过补贴
    remark = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)


class FileStorage(Base):
    __tablename__ = "file_storage"
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf/word/excel/image/other
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100))
    business_type = Column(String(50))  # title_certificate / subsidy_policy / subsidy_voucher
    business_id = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("sys_user.id"))
    uploaded_at = Column(DateTime, default=datetime.now)
    is_encrypted = Column(Boolean, default=False)
    checksum = Column(String(64))


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    user_name = Column(String(50))
    action = Column(String(20), nullable=False)  # create/update/delete/login/export
    business_type = Column(String(50))
    business_id = Column(Integer)
    before_value = Column(Text)  # JSON
    after_value = Column(Text)   # JSON
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    created_at = Column(DateTime, default=datetime.now)


class Reminder(Base):
    __tablename__ = "reminder"
    id = Column(Integer, primary_key=True, autoincrement=True)
    business_type = Column(String(50))  # subsidy_confirm / policy_expire / migration
    business_id = Column(Integer)
    remind_type = Column(String(20))
    title = Column(String(200))
    content = Column(Text)
    remind_at = Column(DateTime)
    status = Column(String(20), default="pending")  # pending/read/ignored
    channel = Column(String(20), default="in_app")  # in_app only (no email)
    user_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)


# ===== 职称 =====
class EmployeeTitle(Base):
    __tablename__ = "employee_title"
    id = Column(Integer, primary_key=True, autoincrement=True)
    seq_no = Column(Integer)
    name = Column(String(50), nullable=False, index=True)
    education = Column(String(50))  # Master/PhD/Bachelor/本科/大专
    title_name = Column(String(100), nullable=False, index=True)  # 工程师/高级工程师/...
    title_series = Column(String(30), nullable=False, index=True)  # engineering/technician
    title_level = Column(String(30), nullable=False, index=True)
    title_date = Column(Date)
    major_field = Column(String(200))   # 专业（手动维护）
    discipline = Column(String(200))    # 学科（手动维护）
    next_stage_apply = Column(String(100))  # 下一阶段申请（人工记录）
    remark = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    certificates = relationship("TitleCertificate", back_populates="title", cascade="all, delete-orphan")


class TitleCertificate(Base):
    __tablename__ = "title_certificate"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey("employee_title.id"), nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("file_storage.id"))
    cert_type = Column(String(30))  # 评定证书/资格证书/扫描件
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    title = relationship("EmployeeTitle", back_populates="certificates")
    file = relationship("FileStorage", foreign_keys=[file_id])


# ===== 人才账号 =====
class TalentAccount(Base):
    __tablename__ = "talent_account"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employee.id"))
    name = Column(String(50), nullable=False, index=True)
    digital_bank = Column(String(100))          # 数币开户行
    digital_account_encrypted = Column(Text)    # 数币账号（加密）
    digital_account_mask = Column(String(30))   # 脱敏缓存
    bank_name = Column(String(100))             # 普通开户行
    bank_account_encrypted = Column(Text)       # 银行卡号（加密）
    bank_account_mask = Column(String(30))      # 脱敏缓存
    has_subsidy = Column(Boolean, default=True)
    remark = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    employee = relationship("Employee", foreign_keys=[employee_id])


# ===== 补贴政策 =====
class SubsidyPolicy(Base):
    __tablename__ = "subsidy_policy"
    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_name = Column(String(200), nullable=False, index=True)
    policy_category = Column(String(50), index=True)  # 薪酬补贴/紧缺人才/租房/房票/...
    region = Column(String(100))
    region_level = Column(String(20))  # 市级/区级/县级
    folder_name = Column(String(200))  # 对应政策扫描目录（POLICY_SCAN_ROOT）下的文件夹名
    valid_from = Column(Date)
    valid_until = Column(Date)
    source_file_id = Column(Integer, ForeignKey("file_storage.id"))
    raw_text = Column(Text)              # PDF 提取原文
    ai_status = Column(String(20), default="pending")  # pending/parsed/confirmed
    status = Column(String(20), default="active")      # active/ended
    remark = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    rules = relationship("SubsidyRule", back_populates="policy", cascade="all, delete-orphan")
    source_file = relationship("FileStorage", foreign_keys=[source_file_id])


class SubsidyRule(Base):
    __tablename__ = "subsidy_rule"
    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_id = Column(Integer, ForeignKey("subsidy_policy.id"), nullable=True, index=True)
    rule_type = Column(String(30), nullable=False)  # cycle/amount/condition/duration/deduction/special
    rule_key = Column(String(100))
    rule_value = Column(Text)      # JSON
    rule_desc = Column(Text)
    source_quote = Column(Text)    # 原文引用
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    policy = relationship("SubsidyPolicy", back_populates="rules")


class SubsidyApplication(Base):
    __tablename__ = "subsidy_application"
    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employee.id"))
    policy_id = Column(Integer, ForeignKey("subsidy_policy.id"), nullable=True, index=True)
    name = Column(String(50), nullable=False, index=True)
    bu = Column(String(50))
    department = Column(String(100))
    hire_date = Column(Date)
    social_security_start = Column(Date)
    awarded_date = Column(Date)
    award_level = Column(String(50))
    total_expected = Column(Float, default=0)
    total_received = Column(Float, default=0)
    status = Column(String(20), default="ongoing")  # ongoing/completed/ended/stopped/resigned
    pending_confirm_by = Column(Integer)
    pending_confirm_at = Column(DateTime)
    remark = Column(Text)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    policy = relationship("SubsidyPolicy")
    employee = relationship("Employee", foreign_keys=[employee_id])
    payments = relationship("SubsidyPayment", back_populates="application", cascade="all, delete-orphan")


class SubsidyPayment(Base):
    __tablename__ = "subsidy_payment"
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("subsidy_application.id"), nullable=False, index=True)
    payment_index = Column(Integer, nullable=False)  # 第几期/第几笔
    expected_date = Column(Date)
    actual_date = Column(Date)
    amount = Column(Float, nullable=False, default=0)
    status = Column(String(20), default="pending")  # pending/pending_confirm/confirmed/paid/stopped/unpaid/completed
    conflict_flag = Column(Boolean, default=False)
    source_rule_id = Column(Integer, ForeignKey("subsidy_rule.id"))
    voucher_file_id = Column(Integer, ForeignKey("file_storage.id"))
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    application = relationship("SubsidyApplication", back_populates="payments")
    comments = relationship("PaymentComment", back_populates="payment", cascade="all, delete-orphan")


class PaymentComment(Base):
    __tablename__ = "payment_comment"
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("subsidy_payment.id"), nullable=False, index=True)
    author = Column(String(50))       # 批注作者（如 jessi.pan）
    content = Column(Text, nullable=False)
    source = Column(String(20), default="manual")  # imported(Excel导入)/manual(系统追加)
    created_at = Column(DateTime, default=datetime.now)

    payment = relationship("SubsidyPayment", back_populates="comments")


class SubsidyConflict(Base):
    __tablename__ = "subsidy_conflict"
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("subsidy_application.id"), nullable=False, index=True)
    conflict_policy_id = Column(Integer, ForeignKey("subsidy_policy.id"))
    conflict_type = Column(String(30))  # 互斥择一/扣减/抵扣
    deduction_amount = Column(Float, default=0)
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    application = relationship("SubsidyApplication")
    conflict_policy = relationship("SubsidyPolicy", foreign_keys=[conflict_policy_id])
