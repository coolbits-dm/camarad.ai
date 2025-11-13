import argon2 from 'argon2';
import { logger } from '../config/logger';

/**
 * Hash password using Argon2id (OWASP recommended)
 */
export async function hashPassword(password: string): Promise<string> {
  try {
    const hash = await argon2.hash(password, {
      type: argon2.argon2id,
      memoryCost: 65536, // 64 MB
      timeCost: 3,
      parallelism: 4,
    });
    return hash;
  } catch (error) {
    logger.error({ error }, 'Failed to hash password');
    throw new Error('Failed to hash password');
  }
}

/**
 * Verify password against hash
 */
export async function verifyPassword(hash: string, password: string): Promise<boolean> {
  try {
    return await argon2.verify(hash, password);
  } catch (error) {
    logger.error({ error }, 'Failed to verify password');
    return false;
  }
}
