import { NextRequest, NextResponse } from "next/server";
import { previewAccess } from "@/lib/preview-access";

export function proxy(request: NextRequest) {
  const denied = previewAccess(request);
  if (denied) return denied;
  const response = NextResponse.next();
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
