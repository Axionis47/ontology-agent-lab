"use client";

import { useState } from "react";
import { api, type Connection, type ConnectionInput } from "@/lib/api";

export function useMcpActions(
  user: string,
  taskId: string,
  onReload: () => Promise<void>,
  onError: (message: string) => void,
) {
  const [busy, setBusy] = useState<string | null>(null);
  const base = `/tasks/${taskId}/connections`;

  async function reconnect(id: string) {
    setBusy(id);
    onError("");
    try {
      await api<Connection>(user, `${base}/${id}/refresh`, "POST");
      await onReload();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function createConnection(input: ConnectionInput) {
    const connection = await api<Connection>(user, base, "POST", input);
    await reconnect(connection.id);
  }

  async function updateToken(id: string, token: string) {
    await api(user, `${base}/${id}/token`, "PUT", { token });
    await reconnect(id);
  }

  async function removeConnection(connection: Connection) {
    if (
      !window.confirm(
        `Remove ${connection.name}? Its tools will be removed from all agents in this task.`,
      )
    )
      return;
    try {
      await api(user, `${base}/${connection.id}`, "DELETE");
      await onReload();
    } catch (e) {
      onError((e as Error).message);
    }
  }

  return {
    busy,
    reconnect,
    createConnection,
    updateToken,
    removeConnection,
  };
}

export type McpActions = ReturnType<typeof useMcpActions>;
