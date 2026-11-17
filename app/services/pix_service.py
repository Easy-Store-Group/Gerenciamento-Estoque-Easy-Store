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

import os
import re
import socket
import urllib.request
import urllib.error
from decimal import Decimal
from typing import Dict, Any


DEFAULT_PIX_KEY_RAW = "(55) 11 98297-4525"
DEFAULT_MERCHANT_NAME = "EASY STORE"
DEFAULT_MERCHANT_CITY = "SAO PAULO"

# Chave de configuração para simulação ou controle de status do Pix
# Pode ser configurada via variáveis de ambiente
# PIX_PROVIDER_URL: URL do endpoint do PSP / Banco para healthcheck (opcional)
# PIX_ENABLED: 'true'/'false' (padrão 'true')
# PIX_KEY: chave Pix personalizada (se configurada)
# PIX_SIMULATE_STATUS: 'ok', 'unavailable', 'timeout', 'error' (para testes / homologação)

def validar_formato_chave_pix(chave: str | None) -> tuple[bool, str]:
    """Valida se a chave Pix informada possui formato aceito pelo BCB.
    
    Aceita: telefone (+55...), CPF (11 dígitos), CNPJ (14 dígitos), email ou chave aleatória (UUIDv4).
    Retorna (valido: bool, motivo: str).
    """
    if not chave or not chave.strip():
        return False, "Chave Pix não informada ou vazia."
    
    limpa = chave.strip()
    
    # 1. Email
    if "@" in limpa and "." in limpa:
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", limpa):
            return True, "Chave Pix do tipo Email válida."
        return False, "Formato de e-mail inválido para chave Pix."
    
    # 2. Chave aleatória EVP (UUID v4: 8-4-4-4-12 hex)
    if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", limpa):
        return True, "Chave Pix do tipo Chave Aleatória (EVP) válida."
    
    # 3. Dígitos (Telefone, CPF ou CNPJ)
    digitos = re.sub(r"\D", "", limpa)
    if len(digitos) == 11:
        return True, "Chave Pix do tipo CPF ou Celular sem DDI válida."
    elif len(digitos) in (12, 13) and digitos.startswith("55"):
        return True, "Chave Pix do tipo Celular com DDI válida."
    elif len(digitos) == 14:
        return True, "Chave Pix do tipo CNPJ válida."
    
    # Se começar com +
    if limpa.startswith("+") and len(digitos) >= 10:
        return True, "Chave Pix telefônica internacional válida."

    return False, "Formato da chave Pix não reconhecido (deve ser telefone, CPF, CNPJ, e-mail ou UUID)."


def verificar_status_pix(timeout: float = 3.0) -> Dict[str, Any]:
    """Verifica a disponibilidade da API / serviço PIX.
    
    Critérios checados:
    1. Se o serviço PIX está habilitado (PIX_ENABLED).
    2. Se a simulação forçada de status está ativa (PIX_SIMULATE_STATUS).
    3. Se a chave Pix configurada é válida.
    4. Se houver URL do provedor configurada (PIX_PROVIDER_URL), testa conexão HTTP com timeout.
    5. Se nenhuma URL externa for configurada, testa geração básica de payload e integridade local.
    """
    # 1. Variável de ativação
    pix_enabled_env = os.getenv("PIX_ENABLED", "true").strip().lower()
    if pix_enabled_env in ("false", "0", "off", "no"):
        return {
            "disponivel": False,
            "motivo": "PIX temporariamente desabilitado pelo administrador do sistema.",
            "codigo": "DESABILITADO",
        }
    
    # 2. Variável de simulação para testes e homologação
    simulacao = os.getenv("PIX_SIMULATE_STATUS", "").strip().lower()
    if simulacao == "unavailable":
        return {
            "disponivel": False,
            "motivo": "PIX temporariamente indisponível. Não foi possível estabelecer conexão com o serviço de pagamento. Escolha outra forma de pagamento ou tente novamente mais tarde.",
            "codigo": "INDISPONIVEL",
        }
    elif simulacao == "timeout":
        return {
            "disponivel": False,
            "motivo": "Tempo limite de conexão esgotado ao contatar o serviço de pagamento PIX (Timeout). Escolha outra forma de pagamento ou tente novamente mais tarde.",
            "codigo": "TIMEOUT",
        }
    elif simulacao == "error":
        return {
            "disponivel": False,
            "motivo": "Falha no provedor de pagamentos PIX. Escolha outra forma de pagamento ou tente novamente mais tarde.",
            "codigo": "ERRO_PROVEDOR",
        }

    # 3. Validação da chave Pix configurada
    chave_configurada = os.getenv("PIX_KEY", DEFAULT_PIX_KEY_RAW)
    valida, motivo_chave = validar_formato_chave_pix(chave_configurada)
    if not valida:
        return {
            "disponivel": False,
            "motivo": f"Configuração PIX inválida: {motivo_chave}. Contate o suporte.",
            "codigo": "CHAVE_INVALIDA",
        }

    # 4. Verificação de conexão com provedor remoto (se configurado)
    provider_url = os.getenv("PIX_PROVIDER_URL", "").strip()
    if provider_url:
        try:
            req = urllib.request.Request(
                provider_url,
                headers={"User-Agent": "EasyStore-PDV/1.0"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status >= 500:
                    return {
                        "disponivel": False,
                        "motivo": "PIX temporariamente indisponível. O provedor retornou erro interno. Escolha outra forma de pagamento ou tente novamente mais tarde.",
                        "codigo": "ERRO_PROVEDOR_HTTP",
                    }
        except urllib.error.HTTPError as he:
            if he.code >= 500:
                return {
                    "disponivel": False,
                    "motivo": "PIX temporariamente indisponível. O provedor retornou erro. Escolha outra forma de pagamento ou tente novamente mais tarde.",
                    "codigo": "HTTP_ERROR",
                }
        except (socket.timeout, urllib.error.URLError, TimeoutError) as te:
            msg_str = str(te).lower()
            if "timed out" in msg_str or isinstance(te, socket.timeout):
                return {
                    "disponivel": False,
                    "motivo": "Tempo limite esgotado ao contatar o serviço PIX. Escolha outra forma de pagamento ou tente novamente mais tarde.",
                    "codigo": "TIMEOUT",
                }
            return {
                "disponivel": False,
                "motivo": "PIX temporariamente indisponível. Não foi possível estabelecer conexão com o serviço de pagamento. Escolha outra forma de pagamento ou tente novamente mais tarde.",
                "codigo": "FALHA_CONEXAO",
            }
        except Exception as ex:
            return {
                "disponivel": False,
                "motivo": f"Falha na comunicação com o provedor PIX: {str(ex)}",
                "codigo": "ERRO_DESCONHECIDO",
            }

    # 5. Validação funcional da geração de QR Code local
    try:
        # Gera teste rápido
        payload_teste = gerar_payload_pix(Decimal("1.00"), chave=chave_configurada)
        if not payload_teste or len(payload_teste) < 30:
            return {
                "disponivel": False,
                "motivo": "Erro ao compor o payload padrão do Banco Central para o PIX.",
                "codigo": "FALHA_PAYLOAD",
            }
    except Exception as exc_payload:
        return {
            "disponivel": False,
            "motivo": f"Erro interno no serviço PIX: {str(exc_payload)}",
            "codigo": "EXCECAO_LOCAL",
        }

    return {
        "disponivel": True,
        "motivo": "Serviço PIX operacional e pronto para cobranças.",
        "codigo": "OPERACIONAL",
        "chave": formatar_chave_pix(chave_configurada),
    }


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

