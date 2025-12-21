import os

from phi2_lab.platform.database import get_database_url


def test_get_database_url_normalizes_postgres_scheme(monkeypatch):
    monkeypatch.setenv("PHILAB_DATABASE_URL", "postgres://user:pass@host:5432/db")
    assert get_database_url().startswith("postgresql://")


def test_get_database_url_passes_postgresql_scheme(monkeypatch):
    monkeypatch.setenv("PHILAB_DATABASE_URL", "postgresql://user:pass@host:5432/db")
    assert get_database_url() == "postgresql://user:pass@host:5432/db"


def test_get_database_url_uses_database_url_fallback(monkeypatch):
    monkeypatch.delenv("PHILAB_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@host:5432/db")
    assert get_database_url().startswith("postgresql://")


def test_get_database_url_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("PHILAB_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url().startswith("sqlite:///")

