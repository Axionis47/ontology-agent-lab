CREATE TABLE model_runtime_checks (
    id uuid PRIMARY KEY,
    config_digest text NOT NULL,
    model text NOT NULL,
    status text NOT NULL CHECK (status IN ('checking', 'connected', 'check_failed')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    duration_ms integer,
    error_code text,
    usage jsonb,
    reserved_nanos bigint NOT NULL CHECK (reserved_nanos >= 0),
    accounted_nanos bigint NOT NULL CHECK (accounted_nanos >= 0),
    input_rate_nanos integer NOT NULL CHECK (input_rate_nanos > 0),
    output_rate_nanos integer NOT NULL CHECK (output_rate_nanos > 0)
);

CREATE UNIQUE INDEX model_runtime_one_active ON model_runtime_checks ((true))
    WHERE status = 'checking';
CREATE INDEX model_runtime_latest ON model_runtime_checks (started_at DESC);
