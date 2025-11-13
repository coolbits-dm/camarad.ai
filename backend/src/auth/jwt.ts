import { sign, verify, TokenExpiredError, JsonWebTokenError, type SignOptions } from 'jsonwebtoken';
import { env } from '../config/env';
import { JwtPayload } from '../types/auth';
import { logger } from '../config/logger';

/**
 * Generate JWT access token
 */
export function generateAccessToken(payload: JwtPayload): string {
  const options: SignOptions = {
    // @ts-ignore - env.JWT_EXPIRES_IN is validated as string by zod
    expiresIn: env.JWT_EXPIRES_IN,
    issuer: 'camarad-api',
    audience: 'camarad-app',
  };
  return sign(payload, env.JWT_SECRET, options);
}

/**
 * Generate JWT refresh token
 */
export function generateRefreshToken(payload: JwtPayload): string {
  const options: SignOptions = {
    // @ts-ignore - env.JWT_REFRESH_EXPIRES_IN is validated as string by zod
    expiresIn: env.JWT_REFRESH_EXPIRES_IN,
    issuer: 'camarad-api',
    audience: 'camarad-app',
  };
  return sign(payload, env.JWT_SECRET, options);
}

/**
 * Verify JWT token
 */
export function verifyToken(token: string): JwtPayload | null {
  try {
    const decoded = verify(token, env.JWT_SECRET, {
      issuer: 'camarad-api',
      audience: 'camarad-app',
    }) as JwtPayload;
    return decoded;
  } catch (error) {
    if (error instanceof TokenExpiredError) {
      logger.debug('Token expired');
    } else if (error instanceof JsonWebTokenError) {
      logger.debug('Invalid token');
    } else {
      logger.error({ error }, 'Token verification failed');
    }
    return null;
  }
}

/**
 * Extract token from Authorization header or cookie
 */
export function extractToken(authHeader?: string, cookieToken?: string): string | null {
  // Try Authorization header first (Bearer token)
  if (authHeader?.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }
  
  // Fall back to cookie
  if (cookieToken) {
    return cookieToken;
  }
  
  return null;
}
