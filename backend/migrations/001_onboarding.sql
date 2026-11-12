CREATE TABLE IF NOT EXISTS tasks (
  id uuid PRIMARY KEY, name text NOT NULL, objective text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS task_members (
  task_id uuid REFERENCES tasks(id) ON DELETE CASCADE,
  user_id text NOT NULL, PRIMARY KEY (task_id, user_id)
);
CREATE TABLE IF NOT EXISTS agents (
  id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  name text NOT NULL, responsibilities text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (id, task_id)
);
CREATE TABLE IF NOT EXISTS mcp_connections (
  id uuid PRIMARY KEY, task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  name text NOT NULL, url text NOT NULL, auth_mode text NOT NULL,
  secret_id uuid, status text NOT NULL DEFAULT 'disconnected', error text,
  auth_url text, refreshed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (id, task_id),
  UNIQUE (task_id, url),
  CHECK (auth_mode IN ('none', 'token', 'oauth')),
  CHECK (status IN ('disconnected', 'connecting', 'auth_required', 'connected', 'error'))
);
CREATE TABLE IF NOT EXISTS tools (
  id uuid PRIMARY KEY, task_id uuid NOT NULL,
  connection_id uuid NOT NULL, name text NOT NULL, title text,
  description text NOT NULL DEFAULT '', input_schema jsonb NOT NULL DEFAULT '{}',
  available boolean NOT NULL DEFAULT true,
  FOREIGN KEY (connection_id, task_id) REFERENCES mcp_connections(id, task_id)
    ON DELETE CASCADE,
  UNIQUE (connection_id, name), UNIQUE (id, task_id)
);
CREATE TABLE IF NOT EXISTS agent_tools (
  agent_id uuid NOT NULL, tool_id uuid NOT NULL, task_id uuid NOT NULL,
  FOREIGN KEY (agent_id, task_id) REFERENCES agents(id, task_id) ON DELETE CASCADE,
  FOREIGN KEY (tool_id, task_id) REFERENCES tools(id, task_id) ON DELETE CASCADE,
  PRIMARY KEY (agent_id, tool_id)
);
CREATE INDEX IF NOT EXISTS agents_task_idx ON agents(task_id);
CREATE INDEX IF NOT EXISTS connections_task_idx ON mcp_connections(task_id);
CREATE INDEX IF NOT EXISTS tools_task_idx ON tools(task_id);
CREATE INDEX IF NOT EXISTS members_user_idx ON task_members(user_id);

-- The browser uses FastAPI. Database API roles receive no table access.
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tools ENABLE ROW LEVEL SECURITY;
