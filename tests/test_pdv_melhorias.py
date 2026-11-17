import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from decimal import Decimal

from app.database import Base
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.venda import Venda
from app.models.variacao import ProdutoVariacao
from app.services.pix_service import verificar_status_pix, gerar_payload_pix
from app.controllers.pdv_controller import finalizar_venda, api_pix_status, api_pix_qrcode
