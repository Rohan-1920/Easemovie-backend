"""Pytest loads first — skip Firestore startup without credentials."""

from __future__ import annotations

import os

os.environ.setdefault("SKIP_FIRESTORE_STARTUP", "true")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
