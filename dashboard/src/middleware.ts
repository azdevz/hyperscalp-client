import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page and public static assets
  if (
    pathname.startsWith("/sign-in") || 
    pathname.startsWith("/_next") || 
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Get session cookie
  const session = request.cookies.get("session")?.value;
  const adminPassword = process.env.ADMIN_PASSWORD || "admin123";

  // Simple session check: verify cookie matches adminPassword
  if (!session || session !== adminPassword) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    '/((?!_next|[^?]*\\.[^?]*$))',
    // Always run for API routes
    '/(api|trpc)(.*)',
  ],
};
