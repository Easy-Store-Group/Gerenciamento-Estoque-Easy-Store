from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import shutil
from datetime import datetime

from app.database import Session as SessionLocal
from app.models.produto import Produto
from app.models.variacao import ProdutoVariacao
from app.models.cor_tamanho import Cor, Tamanho
from app.services.estoque_service import recalcular_estoque_produto

router = APIRouter(
    prefix="/api",
    tags=["Variações, Cores e Tamanhos"]
)

# Diretório para armazenar imagens de variações
UPLOAD_DIR = "app/static/uploads/variacoes"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== CORES ====================

class CorCreate(BaseModel):
    nome: str
    codigo_hex: str | None = None


class CorResponse(BaseModel):
    id: int
    nome: str
    codigo_hex: str | None
    ativa: bool


@router.get("/cores")
def listar_cores(db: Session = Depends(get_db)):
    """Lista todas as cores cadastradas"""
    return db.query(Cor).filter(Cor.ativa == True).all()


@router.post("/cores")
def criar_cor(cor: CorCreate, db: Session = Depends(get_db)):
    """Cria uma nova cor"""
    existe = db.query(Cor).filter(Cor.nome.ilike(cor.nome)).first()
    if existe:
        raise HTTPException(
            status_code=400,
            detail=f"Cor '{cor.nome}' já existe"
        )
    
    nova_cor = Cor(
        nome=cor.nome,
        codigo_hex=cor.codigo_hex,
        ativa=True
    )
    db.add(nova_cor)
    db.commit()
    db.refresh(nova_cor)
    return nova_cor


@router.put("/cores/{cor_id}")
def atualizar_cor(
    cor_id: int,
    cor: CorCreate,
    db: Session = Depends(get_db)
):
    """Atualiza uma cor existente"""
    db_cor = db.query(Cor).filter(Cor.id == cor_id).first()
    if not db_cor:
        raise HTTPException(status_code=404, detail="Cor não encontrada")
    
    db_cor.nome = cor.nome
    db_cor.codigo_hex = cor.codigo_hex
    db.commit()
    db.refresh(db_cor)
    return db_cor


@router.delete("/cores/{cor_id}")
def deletar_cor(cor_id: int, db: Session = Depends(get_db)):
    """Inativa uma cor"""
    db_cor = db.query(Cor).filter(Cor.id == cor_id).first()
    if not db_cor:
        raise HTTPException(status_code=404, detail="Cor não encontrada")
    
    db_cor.ativa = False
    db.commit()
    return {"mensagem": "Cor deletada com sucesso"}


# ==================== TAMANHOS ====================

class TamanhoCreate(BaseModel):
    nome: str


class TamanhoResponse(BaseModel):
    id: int
    nome: str
    ativa: bool


@router.get("/tamanhos")
def listar_tamanhos(db: Session = Depends(get_db)):
    """Lista todos os tamanhos cadastrados"""
    return db.query(Tamanho).filter(Tamanho.ativa == True).all()


@router.post("/tamanhos")
def criar_tamanho(tamanho: TamanhoCreate, db: Session = Depends(get_db)):
    """Cria um novo tamanho"""
    existe = db.query(Tamanho).filter(Tamanho.nome.ilike(tamanho.nome)).first()
    if existe:
        raise HTTPException(
            status_code=400,
            detail=f"Tamanho '{tamanho.nome}' já existe"
        )
    
    novo_tamanho = Tamanho(
        nome=tamanho.nome,
        ativa=True
    )
    db.add(novo_tamanho)
    db.commit()
    db.refresh(novo_tamanho)
    return novo_tamanho


@router.put("/tamanhos/{tamanho_id}")
def atualizar_tamanho(
    tamanho_id: int,
    tamanho: TamanhoCreate,
    db: Session = Depends(get_db)
):
    """Atualiza um tamanho existente"""
    db_tamanho = db.query(Tamanho).filter(Tamanho.id == tamanho_id).first()
    if not db_tamanho:
        raise HTTPException(status_code=404, detail="Tamanho não encontrado")
    
    db_tamanho.nome = tamanho.nome
    db.commit()
    db.refresh(db_tamanho)
    return db_tamanho


@router.delete("/tamanhos/{tamanho_id}")
def deletar_tamanho(tamanho_id: int, db: Session = Depends(get_db)):
    """Inativa um tamanho"""
    db_tamanho = db.query(Tamanho).filter(Tamanho.id == tamanho_id).first()
    if not db_tamanho:
        raise HTTPException(status_code=404, detail="Tamanho não encontrado")
    
    db_tamanho.ativa = False
    db.commit()
    return {"mensagem": "Tamanho deletado com sucesso"}


# ==================== VARIAÇÕES ====================

@router.get("/produtos")
def listar_produtos_api(db: Session = Depends(get_db)):
    """Lista produtos para os seletores e a gestão de variações."""
    produtos = (
        db.query(Produto)
        .filter(Produto.ativo == True)
        .order_by(Produto.nome)
        .all()
    )
    return [
        {"id": produto.id, "nome": produto.nome, "estoque_atual": produto.estoque_atual}
        for produto in produtos
    ]


@router.get("/produtos/com-variacoes")
def listar_produtos_com_variacoes(db: Session = Depends(get_db)):
    """Lista somente produtos que possuem variações ativas."""
    produtos = (
        db.query(Produto)
        .join(ProdutoVariacao, ProdutoVariacao.produto_id == Produto.id)
        .filter(Produto.ativo == True, ProdutoVariacao.ativa == True)
        .distinct()
        .order_by(Produto.nome)
        .all()
    )
    return [{"id": produto.id, "nome": produto.nome} for produto in produtos]


class VariacaoCreate(BaseModel):
    produto_id: int
    cor_id: int | None = None
    tamanho_id: int | None = None
    estoque_atual: int = 0


class VariacaoResponse(BaseModel):
    id: int
    produto_id: int
    cor_id: int | None
    tamanho_id: int | None
    estoque_atual: int
    ativa: bool
    imagem: str | None = None


@router.post("/variacoes")
def criar_variacao(
    variacao: VariacaoCreate,
    db: Session = Depends(get_db)
):
    """Cria uma variação (combinação de cor e tamanho para um produto)"""
    
    # Valida produto
    produto = db.query(Produto).filter(Produto.id == variacao.produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    # Valida cor
    if variacao.cor_id:
        cor = db.query(Cor).filter(Cor.id == variacao.cor_id).first()
        if not cor:
            raise HTTPException(status_code=404, detail="Cor não encontrada")
    
    # Valida tamanho
    if variacao.tamanho_id:
        tamanho = db.query(Tamanho).filter(Tamanho.id == variacao.tamanho_id).first()
        if not tamanho:
            raise HTTPException(status_code=404, detail="Tamanho não encontrado")
    
    # Verifica duplicação
    existe = db.query(ProdutoVariacao).filter(
        ProdutoVariacao.produto_id == variacao.produto_id,
        ProdutoVariacao.cor_id == variacao.cor_id,
        ProdutoVariacao.tamanho_id == variacao.tamanho_id
    ).first()
    
    if existe:
        raise HTTPException(
            status_code=400,
            detail="Esta combinação de cor e tamanho já existe para este produto"
        )
    
    nova_variacao = ProdutoVariacao(
        produto_id=variacao.produto_id,
        cor_id=variacao.cor_id,
        tamanho_id=variacao.tamanho_id,
        estoque_atual=variacao.estoque_atual,
        ativa=True
    )
    
    db.add(nova_variacao)
    db.flush()
    
    recalcular_estoque_produto(db, variacao.produto_id)
    db.commit()
    db.refresh(nova_variacao)
    
    return nova_variacao


@router.get("/variacoes/produto/{produto_id}")
def listar_variacoes_produto(produto_id: int, db: Session = Depends(get_db)):
    """Lista todas as variações de um produto com detalhes de cor e tamanho"""
    
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    
    variacoes = db.query(ProdutoVariacao).filter(
        ProdutoVariacao.produto_id == produto_id,
        ProdutoVariacao.ativa == True
    ).all()
    
    resultado = []
    for v in variacoes:
        resultado.append({
            "id": v.id,
            "produto_id": v.produto_id,
            "cor": {"id": v.cor.id, "nome": v.cor.nome, "codigo_hex": v.cor.codigo_hex} if v.cor else None,
            "tamanho": {"id": v.tamanho_obj.id, "nome": v.tamanho_obj.nome} if v.tamanho_obj else None,
            "estoque_atual": v.estoque_atual,
            "ativa": v.ativa,
            "imagem": v.imagem
        })
    
    return resultado


@router.get("/variacoes/{variacao_id}")
def obter_variacao(variacao_id: int, db: Session = Depends(get_db)):
    """Obtém detalhes de uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    return {
        "id": variacao.id,
        "produto_id": variacao.produto_id,
        "cor": {"id": variacao.cor.id, "nome": variacao.cor.nome} if variacao.cor else None,
        "tamanho": {"id": variacao.tamanho_obj.id, "nome": variacao.tamanho_obj.nome} if variacao.tamanho_obj else None,
        "estoque_atual": variacao.estoque_atual,
        "ativa": variacao.ativa,
        "imagem": variacao.imagem
    }


@router.put("/variacoes/{variacao_id}")
def atualizar_variacao(
    variacao_id: int,
    estoque: int | None = None,
    ativa: bool | None = None,
    db: Session = Depends(get_db)
):
    """Atualiza estoque ou status de uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    if estoque is not None:
        variacao.estoque_atual = estoque
    
    if ativa is not None:
        variacao.ativa = ativa
    
    recalcular_estoque_produto(db, variacao.produto_id)
    db.commit()
    db.refresh(variacao)
    
    return {"mensagem": "Variação atualizada"}


@router.put("/variacoes/{variacao_id}/entrada")
def entrada_estoque_variacao(
    variacao_id: int,
    quantidade: int,
    db: Session = Depends(get_db)
):
    """Adiciona quantidade ao estoque de uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    variacao.estoque_atual += quantidade
    recalcular_estoque_produto(db, variacao.produto_id)
    db.commit()
    
    return {"mensagem": "Entrada registrada", "estoque": variacao.estoque_atual}


@router.put("/variacoes/{variacao_id}/saida")
def saida_estoque_variacao(
    variacao_id: int,
    quantidade: int,
    db: Session = Depends(get_db)
):
    """Remove quantidade do estoque de uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    if variacao.estoque_atual < quantidade:
        raise HTTPException(status_code=400, detail="Estoque insuficiente")
    
    variacao.estoque_atual -= quantidade
    recalcular_estoque_produto(db, variacao.produto_id)
    db.commit()
    
    return {"mensagem": "Saída registrada", "estoque": variacao.estoque_atual}


@router.post("/variacoes/{variacao_id}/imagem")
def upload_imagem_variacao(
    variacao_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Faz upload de imagem para uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    # Validar tipo de arquivo
    allowed_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
    file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não permitido. Use: {', '.join(allowed_extensions)}"
        )
    
    try:
        # Gerar nome único para o arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"variacao_{variacao_id}_{timestamp}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        
        # Salvar arquivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Deletar imagem antiga se existir
        if variacao.imagem:
            old_path = os.path.join(UPLOAD_DIR, os.path.basename(variacao.imagem))
            if os.path.exists(old_path):
                os.remove(old_path)
        
        # Atualizar caminho da imagem no banco
        variacao.imagem = f"/static/uploads/variacoes/{file_name}"
        db.commit()
        db.refresh(variacao)
        
        return {
            "mensagem": "Imagem enviada com sucesso",
            "imagem": variacao.imagem,
            "variacao_id": variacao.id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao fazer upload: {str(e)}")


@router.delete("/variacoes/{variacao_id}/imagem")
def deletar_imagem_variacao(
    variacao_id: int,
    db: Session = Depends(get_db)
):
    """Deleta a imagem de uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    if variacao.imagem:
        try:
            file_path = os.path.join(UPLOAD_DIR, os.path.basename(variacao.imagem))
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao deletar imagem: {str(e)}")
        
        variacao.imagem = None
        db.commit()
    
    return {"mensagem": "Imagem deletada com sucesso"}


@router.delete("/variacoes/{variacao_id}")
def deletar_variacao(variacao_id: int, db: Session = Depends(get_db)):
    """Deleta uma variação"""
    variacao = db.query(ProdutoVariacao).filter(ProdutoVariacao.id == variacao_id).first()
    
    if not variacao:
        raise HTTPException(status_code=404, detail="Variação não encontrada")
    
    produto_id = variacao.produto_id
    if variacao.imagem:
        caminho_imagem = os.path.join(UPLOAD_DIR, os.path.basename(variacao.imagem))
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

    db.delete(variacao)
    db.flush()
    
    recalcular_estoque_produto(db, produto_id)
    db.commit()
    
    return {"mensagem": "Variação removida com sucesso"}
