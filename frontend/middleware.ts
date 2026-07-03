import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const protectedPaths = ["/app", "/onboarding"];
const authPaths = ["/login"];

function isValidJwt(token: string): boolean {
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  try {
    return parts.every((p) => {
      try {
        atob(p.replace(/-/g, "+").replace(/_/g, "/"));
        return true;
      } catch {
        return false;
      }
    });
  } catch {
    return false;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const raw = request.cookies.get("research-swarm-token")?.value
    || request.headers.get("authorization")?.replace("Bearer ", "")
    || "";
  const token = raw.trim();

  const isProtected = protectedPaths.some((p) => pathname.startsWith(p));
  const isAuth = authPaths.some((p) => pathname.startsWith(p));

  if (isProtected) {
    if (!token || !isValidJwt(token)) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  if (isAuth && token && isValidJwt(token)) {
    return NextResponse.redirect(new URL("/app", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/onboarding", "/login"],
};
