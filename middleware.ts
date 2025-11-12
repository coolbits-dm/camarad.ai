import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const blockedPrefixes = ['/api/relay', '/api/auth', '/secret'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (blockedPrefixes.some((prefix) => pathname.startsWith(prefix))) {
    return new NextResponse('Not Found', { status: 404 });
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
