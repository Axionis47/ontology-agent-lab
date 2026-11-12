CREATE TABLE training_cases (
  id uuid PRIMARY KEY, task_id uuid NOT NULL, agent_id uuid NOT NULL,
  query text NOT NULL, tool_ids jsonb NOT NULL, task_success text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (agent_id,task_id) REFERENCES agents(id,task_id) ON DELETE CASCADE
);
CREATE INDEX training_cases_agent ON training_cases(agent_id,created_at,id);

CREATE TABLE training_runs (
  id uuid PRIMARY KEY, task_id uuid NOT NULL, agent_id uuid NOT NULL,
  request_id uuid NOT NULL UNIQUE, request_digest text NOT NULL, created_by text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('training','inference')),
  discovery_run_id uuid REFERENCES discovery_runs(id), inputs jsonb NOT NULL,
  input_digest text NOT NULL, cases jsonb NOT NULL, limits jsonb NOT NULL,
  environment_ref text, evaluator_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('running','stopping','completed','stopped','failed','interrupted')),
  stage text NOT NULL, message text NOT NULL DEFAULT '',
  accepted_candidate_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (agent_id,task_id) REFERENCES agents(id,task_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX training_active_agent ON training_runs(agent_id)
  WHERE status IN ('running','stopping');
CREATE INDEX training_runs_agent ON training_runs(agent_id,created_at DESC);

CREATE TABLE training_candidates (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  digest text NOT NULL, payload jsonb NOT NULL, patch jsonb,
  status text NOT NULL CHECK (status IN ('provisional','accepted','rejected')),
  decision jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(run_id,digest)
);
ALTER TABLE training_runs ADD FOREIGN KEY (accepted_candidate_id) REFERENCES training_candidates(id);

CREATE TABLE training_episodes (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  case_id uuid NOT NULL, case_snapshot jsonb NOT NULL,
  candidate_id uuid REFERENCES training_candidates(id), round_index integer NOT NULL,
  stage text NOT NULL CHECK (stage IN ('baseline','harness','inference')),
  status text NOT NULL, environment_ref text, result jsonb NOT NULL DEFAULT '{}',
  evaluation jsonb, created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
  UNIQUE(run_id,round_index,case_id)
);
CREATE TABLE training_events (
  sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id uuid NOT NULL UNIQUE, run_id uuid NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  episode_id uuid REFERENCES training_episodes(id) ON DELETE CASCADE,
  kind text NOT NULL, message text NOT NULL DEFAULT '', data jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX training_events_run ON training_events(run_id,sequence);
CREATE TABLE training_calls (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  episode_id uuid REFERENCES training_episodes(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('model','mcp')), request jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('dispatched','succeeded','failed','unknown')),
  response jsonb, usage jsonb, reserved_nanos bigint NOT NULL DEFAULT 0,
  accounted_nanos bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz
);
CREATE INDEX training_calls_run ON training_calls(run_id,created_at);
CREATE TABLE training_credentials (
  id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
  connection_id uuid NOT NULL REFERENCES mcp_connections(id) ON DELETE CASCADE,
  encrypted_value text, vault_id uuid
);
ALTER TABLE training_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_episodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_credentials ENABLE ROW LEVEL SECURITY;
