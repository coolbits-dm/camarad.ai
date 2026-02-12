import { FastifyRequest, FastifyReply } from 'fastify';
import { authService } from './auth.service';
import { emailService } from './email.service';
import { RegisterSchema, LoginSchema } from '../types/auth';
import { env } from '../config/env';

export class AuthController {
  /**
   * POST /auth/register
   */
  async register(request: FastifyRequest, reply: FastifyReply) {
    try {
      const input = RegisterSchema.parse(request.body);
      const result = await authService.register(input);

      // Set HTTP-only cookie
      reply.setCookie('access_token', result.accessToken, {
        httpOnly: true,
        secure: env.COOKIE_SECURE,
        sameSite: env.COOKIE_SAME_SITE,
        path: '/',
        domain: env.COOKIE_DOMAIN,
        maxAge: 7 * 24 * 60 * 60, // 7 days
      });

      return reply.code(201).send({
        success: true,
        user: result.user,
      });
    } catch (error) {
      if (error instanceof Error) {
        return reply.code(400).send({
          error: 'Registration failed',
          message: error.message,
        });
      }
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * POST /auth/login
   */
  async login(request: FastifyRequest, reply: FastifyReply) {
    try {
      const input = LoginSchema.parse(request.body);
      const ipAddress = request.ip;
      const userAgent = request.headers['user-agent'];

      const result = await authService.login(input, ipAddress, userAgent);

      // Set HTTP-only cookie
      reply.setCookie('access_token', result.accessToken, {
        httpOnly: true,
        secure: env.COOKIE_SECURE,
        sameSite: env.COOKIE_SAME_SITE,
        path: '/',
        domain: env.COOKIE_DOMAIN,
        maxAge: 7 * 24 * 60 * 60, // 7 days
      });

      return reply.code(200).send({
        success: true,
        user: result.user,
      });
    } catch (error) {
      if (error instanceof Error) {
        return reply.code(401).send({
          error: 'Login failed',
          message: error.message,
        });
      }
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * POST /auth/logout
   */
  async logout(request: FastifyRequest, reply: FastifyReply) {
    try {
      const sessionId = request.sessionId;

      if (sessionId) {
        await authService.logout(sessionId);
      }

      // Clear cookie
      reply.clearCookie('access_token', {
        path: '/',
        domain: env.COOKIE_DOMAIN,
      });

      return reply.code(200).send({
        success: true,
        message: 'Logged out successfully',
      });
    } catch (error) {
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * GET /auth/session
   */
  async getSession(request: FastifyRequest, reply: FastifyReply) {
    try {
      const sessionId = request.sessionId;

      if (!sessionId) {
        return reply.code(401).send({
          error: 'Unauthorized',
          message: 'No active session',
        });
      }

      const session = await authService.getSession(sessionId);

      if (!session) {
        return reply.code(401).send({
          error: 'Unauthorized',
          message: 'Invalid or expired session',
        });
      }

      return reply.code(200).send({
        success: true,
        user: session.user,
      });
    } catch (error) {
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * POST /auth/verify-email
   */
  async verifyEmail(request: FastifyRequest<{ Body: { token: string } }>, reply: FastifyReply) {
    try {
      const { token } = request.body;

      if (!token) {
        return reply.code(400).send({
          error: 'Bad request',
          message: 'Verification token is required',
        });
      }

      const success = await emailService.verifyEmail(token);

      if (!success) {
        return reply.code(400).send({
          error: 'Verification failed',
          message: 'Invalid or expired verification token',
        });
      }

      return reply.code(200).send({
        success: true,
        message: 'Email verified successfully',
      });
    } catch (error) {
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * POST /auth/resend-verification
   */
  async resendVerification(request: FastifyRequest, reply: FastifyReply) {
    try {
      const userId = request.userId;

      if (!userId) {
        return reply.code(401).send({
          error: 'Unauthorized',
        });
      }

      await emailService.resendVerificationEmail(userId);

      return reply.code(200).send({
        success: true,
        message: 'Verification email sent',
      });
    } catch (error) {
      if (error instanceof Error) {
        return reply.code(400).send({
          error: 'Resend failed',
          message: error.message,
        });
      }
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }
}

export const authController = new AuthController();
