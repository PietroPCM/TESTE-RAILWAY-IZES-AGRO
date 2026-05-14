"""
Aplica indices/constraints de hardening em bancos existentes.

Uso:
    python scripts/apply_hardening_indexes.py

Seguro para rodar mais de uma vez em PostgreSQL/Supabase.
"""

from sqlalchemy import text

from app.db import engine


POSTGRES_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_sensores_cliente_ativo ON sensores (cliente_id, ativo)",
    "CREATE INDEX IF NOT EXISTS ix_sensores_cliente_local ON sensores (cliente_id, local_especifico)",
    "CREATE INDEX IF NOT EXISTS ix_leituras_cliente_sensor_timestamp ON leituras (cliente_id, sensor_id, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS ix_leituras_cliente_alerta_timestamp ON leituras (cliente_id, alerta_ativo, timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS ix_alertas_cliente_status_criado ON alertas (cliente_id, status, criado_em DESC)",
    "CREATE INDEX IF NOT EXISTS ix_alertas_cliente_severidade_tipo ON alertas (cliente_id, severidade, tipo)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_alertas_hash_deduplicacao ON alertas (hash_deduplicacao) WHERE hash_deduplicacao IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_zonas_cliente_ativo ON zonas_manejo (cliente_id, ativo)",
    "CREATE INDEX IF NOT EXISTS ix_zonas_prop_ativo ON zonas_manejo (prop_id, ativo)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_zonas_manejo_parcel_nome ON zonas_manejo (parcel_id, nome)",
    "CREATE INDEX IF NOT EXISTS ix_agri_farms_cliente_ativo ON agri_farms (cliente_id, ativo)",
    "CREATE INDEX IF NOT EXISTS ix_agri_parcels_cliente_ativo ON agri_parcels (cliente_id, ativo)",
    "CREATE INDEX IF NOT EXISTS ix_agri_parcels_farm_ativo ON agri_parcels (farm_id, ativo)",
]


def main() -> None:
    with engine.begin() as conn:
        for statement in POSTGRES_STATEMENTS:
            conn.execute(text(statement))
    print(f"Hardening aplicado: {len(POSTGRES_STATEMENTS)} statements")


if __name__ == "__main__":
    main()
