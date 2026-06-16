from fastapi import Request, status
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from urllib.parse import quote_plus
import logging

templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)


class NaoAutenticadoError(Exception):
    pass


class PermissaoNegadaError(Exception):
    pass


class RecursoNaoEncontradoError(Exception):
    def __init__(self, recurso: str, mensagem: str | None = None):
        self.recurso = recurso
        self.mensagem = mensagem or f"{recurso} não encontrado"


class EstoqueInsuficienteError(Exception):
    def __init__(self, nome: str, atual: int, requisitado: int):
        self.nome = nome
        self.atual = atual
        self.requisitado = requisitado
        self.mensagem = (
            f"Estoque insuficiente para {nome}: disponível={atual}, requisitado={requisitado}"
        )


class OperacaoInvalidaError(Exception):
    def __init__(self, mensagem: str):
        self.mensagem = mensagem


def _is_api_request(request: Request) -> bool:
    try:
        return request.url.path.startswith("/api/")
    except Exception:
        return False


def handler_nao_autenticado(request: Request, exc: NaoAutenticadoError):
    logger.info("Não autenticado: %s %s", request.method, request.url.path)
    if _is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "nao_autenticado", "mensagem": "Usuário não autenticado."},
        )
    return _render_nao_autenticado(request)


def handler_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        logger.info("Não autenticado: %s %s", request.method, request.url.path)
        if _is_api_request(request):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "nao_autenticado", "mensagem": "Faça login para continuar."},
            )
        return _render_nao_autenticado(request)

    if exc.status_code == status.HTTP_403_FORBIDDEN:
        logger.warning("Permissão negada: %s %s", request.method, request.url.path)
        if _is_api_request(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "permissao_negada", "mensagem": str(exc.detail)},
            )
        html = templates.env.get_template("errors/erro.html").render(
            {"request": request, "codigo": 403, "titulo": "Permissão negada", "mensagem": str(exc.detail)}
        )
        return HTMLResponse(content=html, status_code=status.HTTP_403_FORBIDDEN)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


def _render_nao_autenticado(request: Request):
    html = templates.env.get_template("errors/nao_autenticado.html").render(
        {"request": request, "next_url": request.url.path}
    )
    return HTMLResponse(content=html, status_code=status.HTTP_401_UNAUTHORIZED)


def handler_permissao_negada(request: Request, exc: PermissaoNegadaError):
    logger.warning("Permissão negada: %s %s", request.method, request.url.path)
    if _is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "permissao_negada", "mensagem": "Ação não permitida."},
        )
    html = templates.env.get_template("errors/erro.html").render(
        {"request": request, "codigo": 403, "titulo": "Permissão negada", "mensagem": "Você não tem permissão para realizar esta ação."}
    )
    return HTMLResponse(content=html, status_code=status.HTTP_403_FORBIDDEN)


def handler_recurso_nao_encontrado(request: Request, exc: RecursoNaoEncontradoError):
    logger.info("Recurso não encontrado: %s - %s", getattr(exc, "recurso", ""), request.url.path)
    mensagem = getattr(exc, "mensagem", "Recurso não encontrado")
    if _is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "recurso_nao_encontrado", "mensagem": mensagem},
        )
    html = templates.env.get_template("errors/erro.html").render(
        {"request": request, "codigo": 404, "titulo": "Não encontrado", "mensagem": mensagem}
    )
    return HTMLResponse(content=html, status_code=status.HTTP_404_NOT_FOUND)


def handler_estoque_insuficiente(request: Request, exc: EstoqueInsuficienteError):
    logger.info("Estoque insuficiente: %s - %s", getattr(exc, "nome", ""), request.url.path)
    mensagem = getattr(exc, "mensagem", "Estoque insuficiente")
    if _is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "estoque_insuficiente", "mensagem": mensagem},
        )
    html = templates.env.get_template("errors/erro.html").render(
        {"request": request, "codigo": 422, "titulo": "Estoque insuficiente", "mensagem": mensagem}
    )
    return HTMLResponse(content=html, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def handler_operacao_invalida(request: Request, exc: OperacaoInvalidaError):
    logger.info("Operação inválida: %s - %s", getattr(exc, "mensagem", ""), request.url.path)
    mensagem = getattr(exc, "mensagem", "Operação inválida")
    if _is_api_request(request):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "operacao_invalida", "mensagem": mensagem},
        )
    # Para requisições HTML, redireciona de volta para a página anterior
    referer = request.headers.get("referer") or "/produtos"
    encoded = quote_plus(mensagem)
    sep = "&" if "?" in referer else "?"
    return RedirectResponse(url=f"{referer}{sep}erro={encoded}", status_code=status.HTTP_303_SEE_OTHER)


__all__ = [
    "NaoAutenticadoError",
    "PermissaoNegadaError",
    "RecursoNaoEncontradoError",
    "EstoqueInsuficienteError",
    "OperacaoInvalidaError",
    "handler_nao_autenticado",
    "handler_http_exception",
    "handler_permissao_negada",
    "handler_recurso_nao_encontrado",
    "handler_estoque_insuficiente",
    "handler_operacao_invalida",
]
