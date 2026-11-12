export function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function text(value: unknown, fallback = ""): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : fallback;
}

export function SavedData({
  title,
  value,
  open = false,
}: {
  title: string;
  value: unknown;
  open?: boolean;
}) {
  return (
    <details open={open} className="min-w-0 border p-3 text-xs">
      <summary className="cursor-pointer break-words font-medium">
        {title}
      </summary>
      <pre
        tabIndex={0}
        className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all text-[11px] leading-5"
      >
        {JSON.stringify(value, null, 2) ?? "No saved data."}
      </pre>
    </details>
  );
}
