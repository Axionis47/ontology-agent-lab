"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ConnectionInput } from "@/lib/api";

export function ConfigurationDialog({
  kind,
  trigger,
  initial,
  onSave,
}: {
  kind: "task" | "agent";
  trigger: ReactNode;
  initial?: { name: string; text: string };
  onSave: (name: string, text: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const title = `${initial ? "Edit" : "Create"} ${kind}`;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await onSave(String(data.get("name")), String(data.get("text")));
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) {
          setOpen(value);
          setError("");
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {kind === "task"
              ? "Define the objective. Add MCPs and agents inside this task."
              : "Define this agent's responsibilities. Tool access starts empty."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5">
          <label className="field">
            Name
            <Input
              name="name"
              defaultValue={initial?.name}
              required
              maxLength={100}
              autoComplete="off"
              placeholder={
                kind === "task"
                  ? "e.g. Customer research"
                  : "e.g. Research analyst"
              }
            />
          </label>
          <label className="field">
            {kind === "task" ? "Objective" : "Responsibilities"}
            <Textarea
              name="text"
              defaultValue={initial?.text}
              required
              maxLength={kind === "task" ? 5000 : 10000}
              rows={5}
              placeholder={
                kind === "task"
                  ? "What should this task achieve?"
                  : "What is this agent responsible for?"
              }
            />
          </label>
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <div className="flex justify-end">
            <Button disabled={busy} type="submit">
              {busy ? "Saving..." : initial ? "Save changes" : title}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConnectionDialog({
  onSave,
}: {
  onSave: (body: ConnectionInput) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [auth, setAuth] = useState<"none" | "token" | "oauth">("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await onSave({
        name: String(form.get("name")),
        url: String(form.get("url")),
        auth_mode: auth,
        ...(auth === "token" ? { token: String(form.get("token")) } : {}),
      });
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!busy) {
          setOpen(value);
          setError("");
          setAuth("none");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>+ Add MCP</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add MCP</DialogTitle>
          <DialogDescription>
            Connect a remote MCP server to this task&apos;s shared tool catalog.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-5" onSubmit={submit}>
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
            <Select
              value={auth}
              onValueChange={(v) => setAuth(v as typeof auth)}
            >
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
          {auth === "token" && (
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
          )}
          {auth === "oauth" && (
            <p className="text-xs text-muted-foreground">
              After connecting, use Authorize to complete sign-in with the MCP
              provider.
            </p>
          )}
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <div className="flex justify-end">
            <Button type="submit" disabled={busy}>
              {busy ? "Connecting..." : "Connect MCP"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function TokenDialog({
  onSave,
}: {
  onSave: (token: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = String(new FormData(event.currentTarget).get("token"));
    setBusy(true);
    setError("");
    try {
      await onSave(token);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!busy) {
          setOpen(v);
          setError("");
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Update token
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update bearer token</DialogTitle>
          <DialogDescription>
            Save the new token and reconnect to discover tools.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
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
          {error && (
            <p role="alert" className="error-text">
              {error}
            </p>
          )}
          <Button disabled={busy}>
            {busy ? "Connecting..." : "Save and reconnect"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
