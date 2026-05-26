from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os
import datetime

load_dotenv()

# Substitua pela sua URL do Supabase
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///loja.db")

engine = create_engine(DATABASE_URL, 
                       connect_args={"check_same_thread": False})
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db=Session()
    try:
        yield db
    finally:
        db.close()