import psycopg2
import config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_URI = f"postgresql+psycopg2://{config.DATABASE_USER}:{config.DATABASE_PASSWORD}@{config.DATABASE_HOST}:{config.DATABASE_PORT}/{config.DATABASE_NAME}"
engine = create_engine(DB_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# For declarative base import
from sqlalchemy.orm import declarative_base
Base = declarative_base()


def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=config.DATABASE_HOST,
            port=config.DATABASE_PORT,
            dbname=config.DATABASE_NAME,
            user=config.DATABASE_USER,
            password=config.DATABASE_PASSWORD,
        )
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None
