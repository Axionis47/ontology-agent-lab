CREATE TABLE discovery_credentials (
  id uuid PRIMARY KEY,
  run_id uuid NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
  connection_id uuid NOT NULL REFERENCES mcp_connections(id) ON DELETE CASCADE,
  encrypted_value text,
  vault_id uuid,
  CHECK ((encrypted_value IS NULL) <> (vault_id IS NULL))
);
CREATE INDEX discovery_credentials_run ON discovery_credentials(run_id);
ALTER TABLE discovery_credentials ENABLE ROW LEVEL SECURITY;
