import base64
import hashlib
import io
import os
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

import qrcode


# Estrutura de dados para armazenar os detalhes da cobrança Pix gerada
@dataclass
class PixCharge:
    provider_charge_id: str  # ID único para rastreamento interno da cobrança
    qr_code_url: str        # Data URI em Base64 pronto para ser usado diretamente em tags HTML <img>
    qr_code_base64: str     # String Base64 contendo a imagem PNG do QR Code
    copia_cola: str         # Código EMVCo completo (Pix Copia e Cola)
    valor: float            # Valor final cobrado (float)
    status: str = "PENDENTE" # Status inicial do pagamento (padrão: "PENDENTE")


class PixService:
    """Gera um BR Code Pix estático com valor e identificador da venda."""

    def __init__(self) -> None:
        # Carrega a chave Pix da variável de ambiente ou utiliza um valor padrão (fallback)
        self.chave_pix = os.getenv("PIX_KEY", "+5511982974525")

    @staticmethod
    def _campo(identificador: str, valor: str) -> str:
        # Formata o campo no padrão EMVCo (TLV: Tag + Tamanho com 2 dígitos + Valor)
        return f"{identificador}{len(valor):02d}{valor}"

    @staticmethod
    def _crc16(payload: str) -> str:
        # Algoritmo de validação CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF) exigido pelo Banco Central
        crc = 0xFFFF
        for byte in payload.encode("utf-8"):
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
        # Retorna o checksum formatado em hexadecimal com 4 caracteres maiúsculos
        return f"{crc:04X}"

    def gerar_cobranca(self, venda_id: int, valor: float) -> PixCharge:
        # Converte o valor para Decimal e ajusta com precisão de 2 casas decimais (arredondamento financeiro)
        valor_decimal = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # Lança erro se o valor for nulo ou negativo
        if valor_decimal <= 0:
            raise ValueError("valor_pix_invalido")

        # Remove espaços da chave Pix e adiciona o caractere '+' caso seja um número de telefone puro
        chave = self.chave_pix.strip()
        if chave.isdigit():
            chave = "+" + chave

        # Monta a sub-tag 26 (Informações do recebedor: Domínio do BCB + Chave Pix)
        conta_pix = self._campo("00", "BR.GOV.BCB.PIX") + self._campo("01", chave)
        
        # Monta a sub-tag 62 (Campo de dados adicionais: ID da transação limitado a 25 caracteres)
        dados_adicionais = self._campo("05", str(venda_id)[:25])

        # Monta o payload completo seguindo as tags estipuladas pelo padrão BR Code / EMVCo
        payload = (
            self._campo("00", "01")              # Payload Format Indicator (versão 01)
            + self._campo("01", "12")           # Point of Initiation Method (12 = reutilizável/estático com valor)
            + self._campo("26", conta_pix)      # Dados da conta do recebedor
            + self._campo("52", "0000")         # Merchant Category Code (0000 = formato geral)
            + self._campo("53", "986")          # Moeda da transação (986 = Real BRL)
            + self._campo("54", f"{valor_decimal:.2f}") # Valor da cobrança formatado
            + self._campo("58", "BR")           # Código do país (BR)
            + self._campo("59", "Easy Store")   # Nome do recebedor/loja
            + self._campo("60", "Sao Paulo")    # Cidade do recebedor
            + self._campo("62", dados_adicionais) # Identificador da venda
            + "6304"                            # Tag ID 63 + tamanho 04 (indica início da soma de verificação CRC16)
        )
        # Gera o código Copia e Cola final anexando o checksum CRC16 calculado no fim da string
        copia_cola = payload + self._crc16(payload)

        # Inicializa a matriz do QR Code com tamanho dos blocos e margens estipulados
        qr = qrcode.QRCode(box_size=8, border=4)
        qr.add_data(copia_cola)
        qr.make(fit=True)
        imagem = qr.make_image(fill_color="black", back_color="white")

        # Retorna a imagem em memória; nenhuma cobrança externa é criada aqui.
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        charge_id = hashlib.sha256(
            f"{venda_id}:{valor_decimal}:{uuid.uuid4().hex}".encode("utf-8")
        ).hexdigest()
        return PixCharge(
            provider_charge_id=charge_id,
            qr_code_url=f"data:image/png;base64,{qr_code_base64}",
            qr_code_base64=qr_code_base64,
            copia_cola=copia_cola,
            valor=float(valor_decimal),
        )
