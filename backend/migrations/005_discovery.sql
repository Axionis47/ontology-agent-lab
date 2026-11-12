ALTER TABLE tools ADD COLUMN output_schema jsonb;
ALTER TABLE tools ADD COLUMN annotations jsonb;

CREATE TABLE discovery_runs (
  id uuid PRIMARY KEY, task_id uuid NOT NULL, agent_id uuid NOT NULL,
  start_request_id uuid NOT NULL UNIQUE, created_by text NOT NULL,
  environment text NOT NULL, inputs jsonb NOT NULL, input_digest text NOT NULL,
  model_digest text NOT NULL, limits jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('running','pausing','paused','completed','stopped')),
  stage text NOT NULL DEFAULT 'inputs', reason text, message text,
  revision integer NOT NULL DEFAULT 1, checkpoint jsonb NOT NULL DEFAULT '{}',
  active_ms bigint NOT NULL DEFAULT 0, active_since timestamptz,
  clarification_rounds integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (agent_id, task_id) REFERENCES agents(id, task_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX discovery_executing ON discovery_runs ((true))
  WHERE status IN ('running','pausing');
CREATE UNIQUE INDEX discovery_unfinished_agent ON discovery_runs (agent_id)
  WHERE status IN ('running','pausing','paused');
CREATE INDEX discovery_history ON discovery_runs (agent_id, created_at DESC);

CREATE TABLE discovery_calls (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('model','mcp')), purpose text NOT NULL,
  tool_id uuid, effect text, request jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('dispatched','succeeded','failed','unknown')),
  response_artifact_id uuid, error_code text, duration_ms integer, usage jsonb,
  reserved_nanos bigint NOT NULL DEFAULT 0 CHECK (reserved_nanos >= 0),
  accounted_nanos bigint NOT NULL DEFAULT 0 CHECK (accounted_nanos >= 0),
  input_rate_nanos integer, output_rate_nanos integer,
  created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE INDEX discovery_calls_run ON discovery_calls(run_id, created_at);

CREATE TABLE discovery_artifacts (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
  kind text NOT NULL, title text NOT NULL, payload jsonb NOT NULL,
  digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE discovery_calls ADD FOREIGN KEY (response_artifact_id) REFERENCES discovery_artifacts(id);
CREATE INDEX discovery_artifacts_run ON discovery_artifacts(run_id, created_at);

CREATE TABLE discovery_questions (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
  round integer NOT NULL, question jsonb NOT NULL,
  answer text, answered_by text, answered_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE discovery_events (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
  kind text NOT NULL, message text NOT NULL, data jsonb NOT NULL DEFAULT '{}',
  request_id uuid UNIQUE, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX discovery_events_run ON discovery_events(run_id, sequence);

ALTER TABLE discovery_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE discovery_events ENABLE ROW LEVEL SECURITY;
