"""Modelos de dados para o modulo de pagamentos do PDV."""

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PaymentMethod(str, Enum):
    DINHEIRO = "dinheiro"
    PIX = "pix"
    CARTAO_CREDITO = "cartao_credito"
    CARTAO_DEBITO = "cartao_debito"


class InstallmentDetail(BaseModel):
    number: int
    amount: Decimal


class PaymentItem(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(..., decimal_places=2, ge=Decimal("0.01"))
    installments_count: int = Field(default=1, ge=1, le=12)
    installments_detail: List[InstallmentDetail] = Field(default_factory=list)
    pix_payload: Optional[str] = None
    pix_confirmed_manual: bool = False


class SalePaymentSummary(BaseModel):
    sale_total: Decimal = Field(..., decimal_places=2, ge=Decimal("0.00"))
    paid_total: Decimal = Field(..., decimal_places=2, ge=Decimal("0.00"))
    pending_total: Decimal = Field(..., decimal_places=2, ge=Decimal("0.00"))
    is_completed: bool = False
    payments: List[PaymentItem] = Field(default_factory=list)
