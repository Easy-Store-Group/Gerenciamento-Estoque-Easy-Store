from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada. Defina a variável de ambiente no Render ou localmente.")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(DATABASE_URL, **engine_kwargs)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_schema_compatibility():
    """Adiciona colunas ausentes nas tabelas de pagamentos para manter compatibilidade com o banco de produção antigo.

    Isso evita falhas ao inserir vendas quando a base já foi criada por uma migration anterior,
    sem apagar registros ou recriar a tabela inteira.
    """
    inspector = inspect(engine)
    if not inspector.has_table("pagamentos"):
        return

    columns = {column["name"] for column in inspector.get_columns("pagamentos")}
    missing_columns = [
        ("parcelado", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("numero_parcelas", "INTEGER DEFAULT 1"),
        ("valor_parcela", "FLOAT")
    ]

    for column_name, column_type in missing_columns:
        if column_name in columns:
            continue

        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE pagamentos ADD COLUMN {column_name} {column_type}"))


ensure_schema_compatibility()


class Base(DeclarativeBase):
    pass


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()