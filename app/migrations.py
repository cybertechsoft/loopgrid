from sqlalchemy import inspect,text


def _cols(engine,table):
    try:return {c['name'] for c in inspect(engine).get_columns(table)}
    except Exception:return set()


def _add(conn,engine,table,column,ddl,applied):
    c=_cols(engine,table)
    if c and column not in c:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"));applied.append(f"{table}.{column}")


def migrate_schema(engine):
    """Small in-place migrations for local/design-partner upgrades.

    Fresh installs are created from SQLAlchemy metadata. Existing v0.6.x databases are
    migrated conservatively so the v0.8 package can be opened against the same local DB.
    Production deployments should eventually move to versioned Alembic migrations.
    """
    applied=[]
    with engine.begin() as conn:
        _add(conn,engine,'workspaces','retention_days','retention_days INTEGER NOT NULL DEFAULT 90',applied)
        _add(conn,engine,'workspaces','redaction_fields_json',"redaction_fields_json TEXT NOT NULL DEFAULT '[]'",applied)
        _add(conn,engine,'api_keys','scopes',"scopes VARCHAR(240) NOT NULL DEFAULT 'ingest,read'",applied)
        _add(conn,engine,'api_keys','description',"description VARCHAR(500) NOT NULL DEFAULT ''",applied)
        _add(conn,engine,'api_keys','created_by',"created_by VARCHAR(160) NOT NULL DEFAULT 'system'",applied)
        _add(conn,engine,'api_keys','expires_at','expires_at TIMESTAMP NULL',applied)
        _add(conn,engine,'api_keys','rotated_from_key_id','rotated_from_key_id VARCHAR(64) NULL',applied)
        _add(conn,engine,'ledger_events','signature_algorithm',"signature_algorithm VARCHAR(64) NOT NULL DEFAULT 'Ed25519'",applied)
    return applied
