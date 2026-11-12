"use client";
import { useState } from "react";
import { FormDialog } from "@/components/form-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ConnectionInput } from "@/lib/api";

function TokenField() {
  return (
    <label className="field">
      Bearer token
      <Input
        name="token"
        type="password"
        required
        maxLength={16000}
        autoComplete="new-password"
      />
    </label>
  );
}

export function ConnectionDialog({
  onSave,
}: {
  onSave: (body: ConnectionInput) => Promise<void>;
}) {
  const [auth, setAuth] = useState<"none" | "token" | "oauth">("none");
  return (
    <FormDialog
      trigger={<Button>+ Add MCP</Button>}
      title="Add MCP"
      description="Connect a remote MCP server to this task's shared tool catalog."
      submitLabel="Connect MCP"
      busyLabel="Connecting..."
      className="sm:max-w-lg"
      onOpen={() => setAuth("none")}
      onSubmit={(data) =>
        onSave({
          name: String(data.get("name")),
          url: String(data.get("url")),
          auth_mode: auth,
          ...(auth === "token" ? { token: String(data.get("token")) } : {}),
        })
      }
    >
      <label className="field">
        MCP name
        <Input
          name="name"
          required
          maxLength={100}
          placeholder="e.g. Research library"
        />
      </label>
      <label className="field">
        Endpoint URL
        <Input
          name="url"
          type="url"
          required
          maxLength={2048}
          placeholder="https://example.com/mcp"
          autoComplete="off"
        />
      </label>
      <div className="field">
        <label htmlFor="connection-auth">Authentication</label>
        <Select value={auth} onValueChange={(v) => setAuth(v as typeof auth)}>
          <SelectTrigger id="connection-auth" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Public endpoint</SelectItem>
            <SelectItem value="token">Bearer token</SelectItem>
            <SelectItem value="oauth">OAuth</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {auth === "token" && <TokenField />}
      {auth === "oauth" && (
        <p className="text-xs text-muted-foreground">
          After connecting, use Authorize to complete sign-in with the MCP
          provider.
        </p>
      )}
    </FormDialog>
  );
}

export function TokenDialog({
  onSave,
}: {
  onSave: (token: string) => Promise<void>;
}) {
  return (
    <FormDialog
      trigger={
        <Button variant="outline" size="sm">
          Update token
        </Button>
      }
      title="Update bearer token"
      description="Save the new token and reconnect to discover tools."
      submitLabel="Save and reconnect"
      busyLabel="Connecting..."
      onSubmit={(data) => onSave(String(data.get("token")))}
    >
      <TokenField />
    </FormDialog>
  );
}
