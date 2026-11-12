import { ArrowUpRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Connection } from "@/lib/api";
import { TokenDialog } from "./connection-dialogs";

export function ConnectionCard({
  connection,
  busy,
  onRefresh,
  onUpdateToken,
  onRemove,
}: {
  connection: Connection;
  busy: boolean;
  onRefresh: () => void;
  onUpdateToken: (token: string) => Promise<void>;
  onRemove: () => void;
}) {
  return (
    <article
      aria-label={`MCP ${connection.name}`}
      className="border bg-card p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-sm">{connection.name}</h3>
            <span
              className={`status-label ${connection.status === "connected" ? "text-primary" : "text-muted-foreground"}`}
            >
              <span
                className={`status-dot ${connection.status === "connected" ? "status-online" : ""}`}
              />
              {connection.status.replaceAll("_", " ")}
            </span>
          </div>
          <p className="mt-2 break-all text-[11px] text-muted-foreground">
            {connection.url}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {connection.auth_url && (
            <Button asChild size="sm">
              <a
                href={connection.auth_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Authorize
                <ArrowUpRight />
              </a>
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={
              busy ||
              ["connecting", "auth_required"].includes(connection.status)
            }
            onClick={onRefresh}
          >
            <RefreshCw className={busy ? "animate-spin" : ""} />
            {busy ? "Connecting..." : "Refresh tools"}
          </Button>
          {connection.auth_mode === "token" &&
            !["connecting", "auth_required"].includes(connection.status) && (
              <TokenDialog onSave={onUpdateToken} />
            )}
          <Button
            variant="ghost"
            size="sm"
            disabled={
              busy ||
              ["connecting", "auth_required"].includes(connection.status)
            }
            onClick={onRemove}
          >
            Remove
          </Button>
        </div>
      </div>
      {connection.error && (
        <p className="error-text mt-3" role="alert">
          {connection.error}
        </p>
      )}
    </article>
  );
}
