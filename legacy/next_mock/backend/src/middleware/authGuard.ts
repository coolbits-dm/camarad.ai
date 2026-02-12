import { FastifyRequest, FastifyReply } from 'fastify';
import { verifyToken, extractToken } from '../auth/jwt';
import { prisma } from '../db/client';
import { logger } from '../config/logger';

declare module 'fastify' {
  interface FastifyRequest {
    userId?: string;
    sessionId?: string;
  }
}

/**
 * Auth Guard Middleware
 * Verifies JWT token and attaches userId to request
 */
export async function authGuard(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<void> {
  const token = extractToken(
    request.headers.authorization,
    request.cookies.access_token
  );

  if (!token) {
    return reply.code(401).send({
      error: 'Unauthorized',
      message: 'No authentication token provided',
    });
  }

  const payload = verifyToken(token);

  if (!payload) {
    return reply.code(401).send({
      error: 'Unauthorized',
      message: 'Invalid or expired token',
    });
  }

  // Verify session exists and is not expired
  const session = await prisma.session.findUnique({
    where: { id: payload.sessionId },
    select: { expiresAt: true, userId: true },
  });

  if (!session) {
    return reply.code(401).send({
      error: 'Unauthorized',
      message: 'Session not found',
    });
  }

  if (session.expiresAt < new Date()) {
    logger.debug({ sessionId: payload.sessionId }, 'Session expired');
    return reply.code(401).send({
      error: 'Unauthorized',
      message: 'Session expired',
    });
  }

  // Attach user info to request
  request.userId = payload.userId;
  request.sessionId = payload.sessionId;
}
