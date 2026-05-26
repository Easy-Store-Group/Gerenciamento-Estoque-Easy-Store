# 1. Hash e verificação de senhas bcrypt
# 2. Geração do token JWT
# 3. Leitura e validação do token vindo do cookie

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status, Depends
from dotenv import load_dotenv
import os

# Carregar as variaveis de ambiente
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRACAO_MINUTOS = int(os.getenv("ACCESS_TOKEN_EXPIRACAO_MINUTOS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# funções de senha
def hash_senha(senha: str):
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str):
    return pwd_context.verify(senha, senha_hash)

# funções do token
def criar_token(data: dict):
    payload = data.copy()
    # Define quando o token expira
    expira = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRACAO_MINUTOS)
    payload.update({"exp": expira})

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decodificar_token(token: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

# dependencia fastapi
def get_usuario_logado(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nao autenticado"
        )
    try:
        payload = decodificar_token(token)
        email = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalido"
            )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado"
        )

def get_usuario_opcional(request: Request):
    try:
        return get_usuario_logado(request)
    except HTTPException:
        return None
    
def exigir_role(role_necessaria: str):
    def verificar(usuario = Depends(get_usuario_logado)):
        if usuario.get("role") != role_necessaria:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissao negada"
            )
    return verificar


def get_admin(request : Request):
    usuario = get_usuario_logado(request)
    if usuario.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito para administradores"
        )
    return usuario