import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base
from app.models import database  # noqa: F401
from app.security import assert_tenant_access, payload_cliente_id, payload_is_admin


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
