import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
load_dotenv()
URL = os.getenv('DATABASE_URL', 'sqlite:///./unisync.db')
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {})
if URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase):
    pass
def get_db():
    with SessionLocal() as db:
        yield db
