import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, safeReturnPath } from "@/lib/navigation";
export function proxy(request: NextRequest) {
  if (!request.cookies.has(SESSION_COOKIE)) {
    const login = new URL("/login", request.url);
    login.searchParams.set("retorno", safeReturnPath(request.nextUrl.pathname));
    return NextResponse.redirect(login);
  }
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
export const config = {
  matcher: [
    "/painel/:path*",
    "/curriculos/:path*",
    "/complementacoes/:path*",
    "/otimizacoes/:path*",
    "/conta/:path*",
  ],
};
