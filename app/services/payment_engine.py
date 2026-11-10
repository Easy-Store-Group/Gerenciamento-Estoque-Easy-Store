"""Motor de regras, calculos e arredondamentos de pagamentos no PDV."""

from decimal import Decimal, ROUND_FLOOR
from typing import List, Optional

from app.models.payment_schemas import (
    PaymentMethod,
    PaymentItem,
    InstallmentDetail,
    SalePaymentSummary,
)
from app.services.pix_service import gerar_payload_pix


def calcular_parcelas_credito(valor: Decimal, parcelas: int) -> List[InstallmentDetail]:
    """Divide o valor exatamente pelo numero de parcelas (1 a 12).

    Aplica arredondamento para baixo (ROUND_FLOOR) em 2 casas decimais.
    Soma e distribui os centavos excedentes nas primeiras parcelas para garantir
    que a soma das parcelas seja exata.
    """
    if parcelas < 1 or parcelas > 12:
        raise ValueError("Quantidade de parcelas deve ser entre 1 e 12.")

    centavos_totais = int(round(valor * 100))
    centavos_base = centavos_totais // parcelas
    resto = centavos_totais % parcelas

    detalhes = []
    for i in range(1, parcelas + 1):
        centavos_parcela = centavos_base + (1 if i <= resto else 0)
        valor_parcela = (Decimal(centavos_parcela) / Decimal(100)).quantize(Decimal("0.01"))
        detalhes.append(InstallmentDetail(number=i, amount=valor_parcela))

    return detalhes


class PaymentEngine:
    """Motor de controle de recebimento no PDV:

    - Limite de no maximo 2 metodos de pagamento por venda.
    - Preenchimento automatico do saldo restante.
    - Divisao exata de parcelas com distribuicao de centavos.
    - Bloqueio quando o valor exceder o pendente ou na finalizacao com saldo pendente > 0.
    """

    def __init__(self, sale_total: Decimal | float | int | str):
        self.sale_total = Decimal(str(sale_total)).quantize(Decimal("0.01"))
        if self.sale_total < Decimal("0.00"):
            raise ValueError("O total da venda nao pode ser negativo.")
        self.payments: List[PaymentItem] = []

    @property
    def paid_total(self) -> Decimal:
        return sum((item.amount for item in self.payments), Decimal("0.00")).quantize(Decimal("0.01"))

    @property
    def pending_total(self) -> Decimal:
        return (self.sale_total - self.paid_total).quantize(Decimal("0.01"))

    @property
    def is_completed(self) -> bool:
        return self.pending_total == Decimal("0.00") and (len(self.payments) > 0 or self.sale_total == Decimal("0.00"))

    def get_summary(self) -> SalePaymentSummary:
        return SalePaymentSummary(
            sale_total=self.sale_total,
            paid_total=self.paid_total,
            pending_total=self.pending_total,
            is_completed=self.is_completed,
            payments=list(self.payments),
        )

    def sugerir_proximo_valor(self) -> Decimal:
        """Retorna o valor pendente exato para o proximo metodo."""
        return self.pending_total

    def add_payment(
        self,
        method: PaymentMethod | str,
        amount: Optional[Decimal | float | int | str] = None,
        installments_count: int = 1,
        pix_confirmed_manual: bool = False,
    ) -> PaymentItem:
        """Adiciona um pagamento a venda aplicando as regras de bloqueio e calculo."""
        if len(self.payments) >= 2:
            raise ValueError("Limite de no maximo 2 metodos de pagamento combinados por venda excedido.")

        if isinstance(method, str):
            method = PaymentMethod(method)

        # Regra de metodos distintos por venda
        if any(p.method == method for p in self.payments):
            raise ValueError("Nao e permitido repetir o mesmo metodo de pagamento na mesma venda.")

        if amount is None:
            amount_dec = self.pending_total
        else:
            amount_dec = Decimal(str(amount)).quantize(Decimal("0.01"))

        if amount_dec <= Decimal("0.00"):
            raise ValueError("O valor do pagamento deve ser maior que zero.")

        if amount_dec > self.pending_total:
            raise ValueError(f"Valor informado (R$ {amount_dec}) excede o saldo pendente (R$ {self.pending_total}).")

        if method == PaymentMethod.CARTAO_CREDITO:
            if installments_count < 1 or installments_count > 12:
                raise ValueError("Cartao de Credito permite de 1 a 12 parcelas.")
            installments_detail = calcular_parcelas_credito(amount_dec, installments_count)
        else:
            installments_count = 1
            installments_detail = []

        pix_payload = None
        if method == PaymentMethod.PIX:
            pix_payload = gerar_payload_pix(amount_dec)

        item = PaymentItem(
            method=method,
            amount=amount_dec,
            installments_count=installments_count,
            installments_detail=installments_detail,
            pix_payload=pix_payload,
            pix_confirmed_manual=pix_confirmed_manual if method == PaymentMethod.PIX else False,
        )

        self.payments.append(item)
        return item


    def validate_finalize(self) -> None:
        """Valida se a venda pode ser encerrada."""
        if self.pending_total > Decimal("0.00"):
            raise ValueError(f"Venda nao pode ser finalizada com saldo pendente de R$ {self.pending_total}.")
        if len(self.payments) > 2:
            raise ValueError("Nao e permitido mais de 2 metodos de pagamento.")
