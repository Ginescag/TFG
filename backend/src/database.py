from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import settings

# 1. EL MOTOR (Engine)
engine = create_engine(settings.database_url)

# 2. LA FÁBRICA DE SESIONES (SessionLocal)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. LA BASE DE LOS MODELOS (Base)
Base = declarative_base()

# 4. EL GENERADOR DE DEPENDENCIAS
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()