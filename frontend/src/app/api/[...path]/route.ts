import type { NextRequest } from "next/server";
import { previewAccess } from "@/lib/preview-access";

export const maxDuration = 60;

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const denied = previewAccess(request);
  if (denied) return denied;
  const { path } = await context.params;
  if (path.some((part) => !/^[a-zA-Z0-9-]+$/.test(part))) {
    return Response.json({ detail: "Invalid API path." }, { status: 400 });
  }
  const mutation = !["GET", "HEAD"].includes(request.method);
  if (mutation && request.headers.get("origin") !== request.nextUrl.origin) {
    return Response.json(
      { detail: "Send changes from the Oak application." },
      { status: 403 },
    );
  }
  const user = request.headers.get("x-oak-user") || "demo-alex";
  if (!["demo-alex", "demo-sam"].includes(user)) {
    return Response.json(
      { detail: "Select a valid demo user." },
      { status: 401 },
    );
  }
  const backend = process.env.OAK_API_URL;
  const key = process.env.OAK_API_KEY;
  if (!backend || !key)
    return Response.json(
      { detail: "The backend is not configured." },
      { status: 503 },
    );
  const body = mutation ? await request.text() : undefined;
  if (body && Buffer.byteLength(body) > 1_000_000) {
    return Response.json(
      { detail: "The request is too large." },
      { status: 413 },
    );
  }
  try {
    const response = await fetch(
      `${backend}/api/${path.join("/")}${request.nextUrl.search}`,
      {
        method: request.method,
        headers: {
          "Content-Type": "application/json",
          "X-Oak-Key": key,
          "X-Oak-User": user,
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(40_000),
        redirect: "error",
      },
    );
    if (response.status >= 500) throw new Error("Backend unavailable");
    return new Response(
      response.status === 204 ? null : await response.text(),
      {
        status: response.status,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
        },
      },
    );
  } catch {
    return Response.json(
      { detail: "The backend is unavailable. Try again shortly." },
      { status: 502 },
    );
  }
}

export {
  forward as GET,
  forward as POST,
  forward as PUT,
  forward as PATCH,
  forward as DELETE,
};
