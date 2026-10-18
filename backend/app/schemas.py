import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_STATE_CODE_RE = re.compile(r"^[0-9]{2}$")


class SignupRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    tenant_slug: str = Field(min_length=2, max_length=63)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)

    @field_validator("tenant_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must be lowercase letters, digits and hyphens")
        return v


class LoginRequest(BaseModel):
    tenant_slug: str
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreateIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    role: str = "member"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"owner", "accountant", "member", "hr", "manager"}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return v


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    role: str


class CompanyIn(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    gstin: str
    state_code: str
    address: str = Field(min_length=1, max_length=500)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: str) -> str:
        if not _GSTIN_RE.match(v):
            raise ValueError("invalid GSTIN format")
        return v

    @field_validator("state_code")
    @classmethod
    def validate_state_code(cls, v: str) -> str:
        if not _STATE_CODE_RE.match(v):
            raise ValueError("state_code must be 2 digits")
        return v


class CompanyOut(CompanyIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = None
    state_code: str
    billing_address: str = Field(min_length=1, max_length=500)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: str | None) -> str | None:
        if v is not None and not _GSTIN_RE.match(v):
            raise ValueError("invalid GSTIN format")
        return v

    @field_validator("state_code")
    @classmethod
    def validate_state_code(cls, v: str) -> str:
        if not _STATE_CODE_RE.match(v):
            raise ValueError("state_code must be 2 digits")
        return v


class CustomerOut(CustomerIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hsn_sac: str = Field(min_length=4, max_length=8)
    unit: str = Field(default="unit", max_length=20)
    unit_price_paise: int = Field(ge=0)
    gst_rate_bps: int = Field(ge=0, le=2800)


class ItemOut(ItemIn):
    model_config = {"from_attributes": True}
    id: uuid.UUID


class LineIn(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(gt=0)


class QuoteIn(BaseModel):
    customer_id: uuid.UUID
    lines: list[LineIn] = Field(min_length=1)


class QuoteLineOut(BaseModel):
    model_config = {"from_attributes": True}
    item_id: uuid.UUID
    quantity: int
    unit_price_paise: int
    gst_rate_bps: int


class QuoteOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    customer_id: uuid.UUID
    lines: list[QuoteLineOut]


class InvoiceIn(BaseModel):
    customer_id: uuid.UUID
    quote_id: uuid.UUID | None = None
    lines: list[LineIn] = Field(min_length=1)


class InvoiceLineOut(BaseModel):
    model_config = {"from_attributes": True}
    item_id: uuid.UUID
    description: str
    hsn_sac: str
    quantity: int
    unit_price_paise: int
    gst_rate_bps: int
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int


class InvoiceOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    customer_id: uuid.UUID
    quote_id: uuid.UUID | None
    status: str
    financial_year: str | None
    number: int | None
    place_of_supply_state_code: str
    subtotal_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    grand_total_paise: int
    created_at: datetime
    issued_at: datetime | None
    cancelled_at: datetime | None
    lines: list[InvoiceLineOut]


class InvoicePreviewOut(BaseModel):
    """Same totals/line shape as InvoiceOut, minus the fields that only exist
    once a draft is actually persisted (id, status, number, ...)."""

    place_of_supply_state_code: str
    subtotal_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    grand_total_paise: int
    lines: list[InvoiceLineOut]


class PaymentIn(BaseModel):
    invoice_id: uuid.UUID
    amount_paise: int = Field(gt=0)
    method: str = Field(min_length=1, max_length=50)
    paid_at: datetime | None = None


class PaymentOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount_paise: int
    method: str
    paid_at: datetime


class TrialBalanceRow(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    debit_paise: int
    credit_paise: int


class AgeingRow(BaseModel):
    invoice_id: uuid.UUID
    financial_year: str | None
    number: int | None
    customer_name: str
    outstanding_paise: int
    days_overdue: int
    bucket: str
