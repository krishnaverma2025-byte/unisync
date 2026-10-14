import pytest
import os,secrets
os.environ["DEMO_PASSWORD"]=secrets.token_urlsafe(24)
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base,get_db
from app.seed import seed
from app.main import app
@pytest.fixture
def db():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def fk(c,r): c.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as db:
        seed(db); yield db
    engine.dispose()
@pytest.fixture
def client(db):
    app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()
def headers(client,email='admin@unisync.local'):
    response=client.post('/auth/login',json={'email':email,'password':os.environ['DEMO_PASSWORD']})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}
