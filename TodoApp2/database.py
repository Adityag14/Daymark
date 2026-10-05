from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import make_url
from dotenv import load_dotenv
import os

load_dotenv()

database_url_value = os.getenv("SQLALCHEMY_DATABASE_URL") or os.getenv("DATABASE_URL")
if not database_url_value:
     if os.getenv("VERCEL"):
          raise RuntimeError("Set SQLALCHEMY_DATABASE_URL or DATABASE_URL in Vercel environment variables.")
     database_url_value = "sqlite:///./todos.db"

database_url = make_url(database_url_value)
if database_url.drivername in {"postgres", "postgresql"}:
     database_url = database_url.set(drivername="postgresql+psycopg2")
SQLALCHEMY_DATABASE_URL = database_url.render_as_string(hide_password=False)

engine_options = {"pool_pre_ping": True}
if database_url.get_backend_name() == "sqlite":
     engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()