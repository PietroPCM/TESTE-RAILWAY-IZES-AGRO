import sys
import os
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.db import Base, DatabaseUrlConfigurationError, SessionLocal, _normalize_database_url, engine
from app.models import database  # noqa: F401
from app.models.database import UsuarioDB
from app.models.user import UserCreate, UserRole
from app.routes.auth_routes import register
from app.security import (
    assert_tenant_access,
    payload_cliente_id,
    payload_is_admin,
    verificar_app_internal_token,
)


def test_tenant_payload_uses_cliente_id_before_subject():
    payload = {"sub": "usuario_1", "cliente_id": "cliente_1", "role": "produtor"}

    assert payload_cliente_id(payload) == "cliente_1"


def test_tenant_access_allows_same_client():
    payload = {"sub": "usuario_1", "cliente_id": "cliente_1", "role": "produtor"}

    assert_tenant_access(payload, "cliente_1")


def test_tenant_access_blocks_other_client():
    payload = {"sub": "usuario_1", "cliente_id": "cliente_1", "role": "produtor"}

    with pytest.raises(HTTPException) as exc:
        assert_tenant_access(payload, "cliente_2")

    assert exc.value.status_code == 403


def test_admin_can_access_any_tenant():
    payload = {"sub": "admin_1", "cliente_id": "cliente_admin", "role": "admin"}

    assert payload_is_admin(payload)
    assert_tenant_access(payload, "cliente_2")


def test_critical_scale_indexes_are_registered():
    expected_indexes = {
        "sensores": {"ix_sensores_cliente_ativo", "ix_sensores_cliente_local"},
        "leituras": {"ix_leituras_cliente_sensor_timestamp", "ix_leituras_cliente_alerta_timestamp"},
        "alertas": {"ix_alertas_cliente_status_criado", "ix_alertas_cliente_severidade_tipo", "ux_alertas_hash_deduplicacao"},
        "zonas_manejo": {"ix_zonas_cliente_ativo", "ix_zonas_prop_ativo"},
    }

    for table_name, index_names in expected_indexes.items():
        table = Base.metadata.tables[table_name]
        registered = {index.name for index in table.indexes}
        assert index_names.issubset(registered)


def test_database_url_normalizes_postgresql_to_psycopg():
    url = _normalize_database_url("postgresql://user:pass@example.internal:5432/appdb")

    assert url == "postgresql+psycopg://user:pass@example.internal:5432/appdb"


def test_database_url_normalizes_postgres_to_psycopg():
    url = _normalize_database_url("postgres://user:pass@example.internal:5432/appdb")

    assert url == "postgresql+psycopg://user:pass@example.internal:5432/appdb"


def test_database_url_keeps_psycopg_v3_url():
    url = _normalize_database_url("postgresql+psycopg://user:pass@example.internal:5432/appdb")

    assert url == "postgresql+psycopg://user:pass@example.internal:5432/appdb"


def test_database_url_rejects_unresolved_railway_reference():
    with pytest.raises(DatabaseUrlConfigurationError) as exc:
        _normalize_database_url("${{Postgres.DATABASE_URL}}")

    message = str(exc.value)
    assert "não foi resolvida" in message
    assert "${{" not in message


def test_database_url_rejects_invalid_literal_without_leaking_value():
    invalid_url = "not-a-valid-database-url"

    with pytest.raises(DatabaseUrlConfigurationError) as exc:
        _normalize_database_url(invalid_url)

    assert invalid_url not in str(exc.value)


def test_public_register_forces_safe_viewer_role():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    email = "privileged-role-request@example.test"
    try:
        db.query(UsuarioDB).filter(UsuarioDB.email == email).delete()
        db.commit()

        response = asyncio.run(register(
            UserCreate(
                email=email,
                nome="Usuario Teste",
                cliente_id="cliente_teste",
                password="senha-segura-teste",
                role=UserRole.ADMIN,
            ),
            db,
        ))

        created = db.query(UsuarioDB).filter(UsuarioDB.email == email).first()
        assert response.role == UserRole.VIEWER
        assert created.role == "viewer"
    finally:
        db.query(UsuarioDB).filter(UsuarioDB.email == email).delete()
        db.commit()
        db.close()


def test_x_app_token_requires_exact_configured_value(monkeypatch):
    monkeypatch.setattr(settings, "app_internal_token", "app_token_esperado")

    assert verificar_app_internal_token("app_token_esperado") == "app_token_esperado"

    with pytest.raises(HTTPException) as exc:
        verificar_app_internal_token("app_qualquer")

    assert exc.value.status_code == 401


def test_x_app_token_fails_closed_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "app_internal_token", "")

    with pytest.raises(HTTPException) as exc:
        verificar_app_internal_token("app_token_esperado")

    assert exc.value.status_code == 503
