"""Each test gets a fresh in-memory database and two users."""
import os

os.environ["DATABASE_URL"] = "sqlite://"  # in memory; set before the app is imported

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import User


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            User(name="Sup", email="sup@test.lab", password_hash=hash_password("pw123456"), role="supervisor"),
            User(name="Tech", email="tech@test.lab", password_hash=hash_password("pw123456"), role="tech"),
        ])
        db.commit()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client, email):
    r = client.post("/api/auth/login", data={"username": email, "password": "pw123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def sup(client):
    return login(client, "sup@test.lab")


@pytest.fixture()
def tech(client):
    return login(client, "tech@test.lab")
