"""
Skelet testləri: konfiqurasiya oxunur, DB qurulur, API qalxır.
LLM olmadan işləyir - ona görə sürətlidir və hər dəfə işlədilə bilər.

İşə salmaq:  pytest -q
"""

import sqlite3

from fastapi.testclient import TestClient

from app.config import settings
from app.db import SCHEMA
from app.main import app


def test_settings_yuklendi():
    assert settings.ollama_model, "OLLAMA_MODEL boşdur — .env faylını yaratmısan?"
    assert settings.base_dir.exists()


def test_db_sxemi_qurulur():
    # Yaddaşda DB yaradırıq ki, real fayla toxunmayaq
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for t in ("stores", "catalogs", "products", "prices", "baskets", "basket_items"):
        assert t in tables, f"{t} cədvəli yaranmadı"
    conn.close()


def test_health_cavab_verir():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        # Ollama sönülü ola bilər -> "degraded" da qəbul edilir
        assert data["status"] in ("ok", "degraded")
        assert "products" in data["database"]


def test_dashboard_acilir():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "BasketIQ" in r.text
