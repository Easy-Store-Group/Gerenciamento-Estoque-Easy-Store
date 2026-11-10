"""Serviço para geração de payload Pix no padrão EMV / BR Code.

Padrão EMV-QRCPS / BR Code (Banco Central do Brasil):
- 00: Payload Format Indicator ("01")
- 26: Merchant Account Information
    - 00: GUI ("br.gov.bcb.pix")
    - 01: Chave Pix
- 52: Merchant Category Code ("0000")
- 53: Transaction Currency ("986" - BRL)
- 54: Transaction Amount (Ex: "10.50")
- 58: Country Code ("BR")
- 59: Merchant Name ("Easy Store" ou similar)
- 60: Merchant City ("SAO PAULO" ou similar)
- 62: Additional Data Field Template
    - 05: Reference Label / txid ("***")
- 63: CRC16 (Tag 6304 seguido do checksum hex maiúsculo)
"""

import re
from decimal import Decimal


DEFAULT_PIX_KEY_RAW = "(55) 11 98297-4525"
DEFAULT_MERCHANT_NAME = "EASY STORE"
DEFAULT_MERCHANT_CITY = "SAO PAULO"


def formatar_chave_pix(chave: str | None = None) -> str:
    """Valida e converte a chave informada para o padrão internacional.

    Exemplo: '(55) 11 98297-4525' -> '+5511982974525'
    """
    if not chave:
        chave = DEFAULT_PIX_KEY_RAW

    # Se for telefone com formato brasileiro ou dígitos
    digitos = re.sub(r"\D", "", chave)
    if digitos:
        # Se começar com 55 e tiver 12 ou 13 dígitos (+55 DDD 9XXXX-XXXX)
        if len(digitos) in (12, 13) and digitos.startswith("55"):
            return f"+{digitos}"
        elif len(digitos) in (10, 11):
            return f"+55{digitos}"
        return f"+{digitos}" if not chave.startswith("+") else chave

    return chave.strip()


def crc16_ccitt(payload: str) -> str:
    """Calcula o checksum CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF).

    Retorna o valor em formato hexadecimal com 4 dígitos maiúsculos.
    """
    crc = 0xFFFF
    for char in payload.encode("utf-8"):
        crc ^= (char << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _format_tlv(tag: str, value: str) -> str:
    """Formata um campo no padrão TLV (Tag-Length-Value)."""
    length = f"{len(value.encode('utf-8')):02d}"
    return f"{tag}{length}{value}"


def gerar_payload_pix(
    valor: Decimal | float | int | str,
    chave: str | None = None,
    nome_recebedor: str = DEFAULT_MERCHANT_NAME,
    cidade_recebedor: str = DEFAULT_MERCHANT_CITY,
    txid: str = "***",
) -> str:
    """Gera o payload copia e cola do Pix estático de acordo com o padrão EMV / BR Code.

    Inclui Tags TLV: 00, 26, 52, 53, 54, 58, 59, 60, 62 e 63 (CRC16).
    """
    chave_formatada = formatar_chave_pix(chave)

    # Sub-tags da conta do recebedor (Tag 26)
    sub_gui = _format_tlv("00", "br.gov.bcb.pix")
    sub_key = _format_tlv("01", chave_formatada)
    tag_26 = _format_tlv("26", f"{sub_gui}{sub_key}")

    tag_00 = _format_tlv("00", "01")
    tag_52 = _format_tlv("52", "0000")
    tag_53 = _format_tlv("53", "986")

    # Formata valor com 2 casas
    val_dec = Decimal(str(valor)).quantize(Decimal("0.01"))
    tag_54 = _format_tlv("54", f"{val_dec:.2f}")

    tag_58 = _format_tlv("58", "BR")
    tag_59 = _format_tlv("59", (nome_recebedor[:25] or "RECEBEDOR").upper())
    tag_60 = _format_tlv("60", (cidade_recebedor[:15] or "SAO PAULO").upper())

    # Tag 62 (Additional Data Field Template)
    sub_txid = _format_tlv("05", txid or "***")
    tag_62 = _format_tlv("62", sub_txid)

    # Concatena sem o CRC
    payload_sem_crc = f"{tag_00}{tag_26}{tag_52}{tag_53}{tag_54}{tag_58}{tag_59}{tag_60}{tag_62}6304"

    # Calcula CRC16
    checksum = crc16_ccitt(payload_sem_crc)
    return f"{payload_sem_crc}{checksum}"


def gerar_qrcode_pix_base64(payload: str) -> str:
    """Gera a imagem PNG do QR code em base64 para exibição na interface."""
    import io
    import base64
    import qrcode

    qr = qrcode.make(payload)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

