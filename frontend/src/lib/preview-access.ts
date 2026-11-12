import { createHash, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

export function previewAccess(request: NextRequest): Response | undefined {
  if (
    process.env.OAK_LOCAL_PREVIEW === "true" &&
    !process.env.VERCEL &&
    process.env.NODE_ENV === "development" &&
    ["localhost", "127.0.0.1"].includes(request.nextUrl.hostname)
  )
    return;

  const user = process.env.OAK_PREVIEW_USER;
  const password = process.env.OAK_PREVIEW_PASSWORD;
  if (!user || !password || password.length < 16) {
    return new Response("Private preview is not configured.", { status: 503 });
  }
  const header = request.headers.get("authorization") || "";
  const supplied = header.startsWith("Basic ")
    ? Buffer.from(header.slice(6), "base64").toString()
    : "";
  const hash = (s: string) => createHash("sha256").update(s).digest();
  if (!timingSafeEqual(hash(supplied), hash(`${user}:${password}`))) {
    return new Response("Private preview access required.", {
      status: 401,
      headers: {
        "WWW-Authenticate":
          'Basic realm="Oak private preview", charset="UTF-8"',
        "Cache-Control": "no-store",
      },
    });
  }
}
