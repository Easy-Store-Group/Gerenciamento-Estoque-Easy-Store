"""Redireciona importações de payment_engine para manter compatibilidade."""

from app.services.payment_engine import (
    PaymentEngine,
    calcular_parcelas_credito,
)

__all__ = ["PaymentEngine", "calcular_parcelas_credito"]
