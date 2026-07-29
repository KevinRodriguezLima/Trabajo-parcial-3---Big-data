-- Event store de la parte B: rastro de auditoría de lo que se publicó.
-- No es el sink de Flink; C decide el suyo por separado.

CREATE TABLE IF NOT EXISTS events (
    -- Los trece campos del contrato v1.0.
    event_id            TEXT        PRIMARY KEY,
    schema_version      TEXT        NOT NULL,
    event_type          TEXT        NOT NULL,
    event_timestamp     TIMESTAMPTZ NOT NULL,
    ingestion_timestamp TIMESTAMPTZ NOT NULL,
    user_id             TEXT        NOT NULL,
    session_id          TEXT        NOT NULL,
    agent_profile       TEXT        NOT NULL,
    source              TEXT        NOT NULL,
    city                TEXT        NOT NULL,
    region              TEXT        NOT NULL,
    scenario            TEXT        NOT NULL,
    payload             JSONB       NOT NULL,
    -- Procedencia en Kafka. `offset` y `partition` son palabras reservadas
    -- en SQL, así que van prefijadas para no tener que citarlas siempre.
    kafka_topic         TEXT        NOT NULL,
    kafka_partition     INTEGER     NOT NULL,
    kafka_offset        BIGINT      NOT NULL,
    stored_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- event_id es la clave primaria: el consumidor es at-least-once y reprocesa
-- tras un reinicio, así que la deduplicación ocurre aquí.
CREATE INDEX IF NOT EXISTS events_event_timestamp_idx ON events (event_timestamp);
CREATE INDEX IF NOT EXISTS events_user_id_idx         ON events (user_id);
CREATE INDEX IF NOT EXISTS events_event_type_idx      ON events (event_type);
CREATE INDEX IF NOT EXISTS events_scenario_idx        ON events (scenario, event_timestamp);
CREATE INDEX IF NOT EXISTS events_source_idx          ON events (source);
-- No es único a propósito: la deduplicación la garantiza event_id, y un
-- segundo índice único daría un conflicto que `ON CONFLICT (event_id)` no
-- captura y tumbaría el lote entero.
CREATE INDEX IF NOT EXISTS events_kafka_coords_idx
    ON events (kafka_topic, kafka_partition, kafka_offset);

CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT        PRIMARY KEY,
    source_file TEXT,
    rate        NUMERIC,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    publicados  BIGINT      NOT NULL DEFAULT 0,
    enviados    BIGINT      NOT NULL DEFAULT 0,
    rechazados  BIGINT      NOT NULL DEFAULT 0,
    fallidos    BIGINT      NOT NULL DEFAULT 0,
    notes       TEXT
);

CREATE INDEX IF NOT EXISTS runs_started_at_idx ON runs (started_at DESC);
