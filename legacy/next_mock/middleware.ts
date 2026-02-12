import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const blockedPrefixes = ['/api/relay', '/api/auth', '/secret'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Block sensitive API routes
  if (blockedPrefixes.some((prefix) => pathname.startsWith(prefix))) {
    return new NextResponse('Not Found', { status: 404 });
  }

  // Note: Authentication checks happen client-side in each page component
  // using the isAuthenticated() function from lib/auth/session.ts
  // This is because we're using Next.js static export with localStorage sessions
  
  // Protected routes that require authentication (handled client-side)
  // - /p/* - Dashboard and panels
  // - /onboarding/* - Onboarding flow
  
  // Auth routes that redirect if authenticated (handled client-side)
  // - /login - Login page
  // - /register - Registration page
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
