"""Pydantic schemas for the talent management system."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


# ===== auth =====
class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


# ===== 职称 =====
class TitleCreate(BaseModel):
    seq_no: Optional[int] = None
    name: str
    education: Optional[str] = None
    title_name: str
    title_series: str  # engineering / technician
    title_level: str
    title_date: Optional[date] = None
    major_field: Optional[str] = None
    discipline: Optional[str] = None
    next_stage_apply: Optional[str] = None
    remark: Optional[str] = None


class TitleUpdate(BaseModel):
    seq_no: Optional[int] = None
    name: Optional[str] = None
    education: Optional[str] = None
    title_name: Optional[str] = None
    title_series: Optional[str] = None
    title_level: Optional[str] = None
    title_date: Optional[date] = None
    major_field: Optional[str] = None
    discipline: Optional[str] = None
    next_stage_apply: Optional[str] = None
    remark: Optional[str] = None


class TitleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    seq_no: Optional[int] = None
    name: str
    education: Optional[str] = None
    title_name: str
    title_series: str
    title_level: str
    title_date: Optional[date] = None
    major_field: Optional[str] = None
    discipline: Optional[str] = None
    next_stage_apply: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


# ===== 人才账号 =====
class TalentAccountCreate(BaseModel):
    name: str
    digital_bank: Optional[str] = None
    digital_account: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    has_subsidy: bool = True
    remark: Optional[str] = None


class TalentAccountUpdate(BaseModel):
    name: Optional[str] = None
    digital_bank: Optional[str] = None
    digital_account: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    has_subsidy: Optional[bool] = None
    remark: Optional[str] = None


class TalentAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    digital_bank: Optional[str] = None
    digital_account_mask: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_mask: Optional[str] = None
    has_subsidy: bool = True
    remark: Optional[str] = None


# ===== 补贴政策 =====
class PolicyCreate(BaseModel):
    policy_name: str
    policy_category: Optional[str] = None
    region: Optional[str] = None
    region_level: Optional[str] = None
    folder_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    status: str = "active"
    remark: Optional[str] = None


class PolicyUpdate(BaseModel):
    policy_name: Optional[str] = None
    policy_category: Optional[str] = None
    region: Optional[str] = None
    region_level: Optional[str] = None
    folder_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    policy_name: str
    policy_category: Optional[str] = None
    region: Optional[str] = None
    region_level: Optional[str] = None
    folder_name: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    ai_status: str = "pending"
    status: str = "active"
    remark: Optional[str] = None


# ===== 补贴申领 / 发放 =====
class ApplicationCreate(BaseModel):
    policy_id: int
    name: str
    bu: Optional[str] = None
    department: Optional[str] = None
    hire_date: Optional[date] = None
    social_security_start: Optional[date] = None
    awarded_date: Optional[date] = None
    award_level: Optional[str] = None
    total_expected: Optional[float] = 0
    status: str = "ongoing"
    remark: Optional[str] = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    policy_id: int
    name: str
    bu: Optional[str] = None
    department: Optional[str] = None
    awarded_date: Optional[date] = None
    award_level: Optional[str] = None
    total_expected: Optional[float] = 0
    total_received: Optional[float] = 0
    status: str = "ongoing"
    remark: Optional[str] = None


class PaymentCreate(BaseModel):
    application_id: int
    payment_index: int
    expected_date: Optional[date] = None
    actual_date: Optional[date] = None
    amount: float = 0
    status: str = "pending"
    conflict_flag: bool = False
    remark: Optional[str] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    payment_index: int
    expected_date: Optional[date] = None
    actual_date: Optional[date] = None
    amount: Optional[float] = 0
    status: str = "pending"
    conflict_flag: bool = False
    remark: Optional[str] = None
