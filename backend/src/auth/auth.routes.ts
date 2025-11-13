import { FastifyInstance } from 'fastify';
import { authController } from './auth.controller';
import { oauthController } from './oauth.controller';
import { authGuard } from '../middleware/authGuard';

export async function authRoutes(app: FastifyInstance) {
  // Public routes
  app.post('/auth/register', async (req, reply) => authController.register(req, reply));
  app.post('/auth/login', async (req, reply) => authController.login(req, reply));

  // OAuth routes
  app.get('/auth/oauth/google/redirect', async (_req, reply) => oauthController.googleRedirect(_req, reply));
  app.get('/auth/oauth/google/callback', async (req, reply) => oauthController.googleCallback(req as any, reply));

  // Email verification routes
  app.post('/auth/verify-email', async (req, reply) => authController.verifyEmail(req as any, reply));

  // Protected routes
  app.post('/auth/resend-verification', {
    preHandler: authGuard,
  }, async (req, reply) => authController.resendVerification(req, reply));

  app.post('/auth/logout', {
    preHandler: authGuard,
  }, async (req, reply) => authController.logout(req, reply));

  app.get('/auth/session', {
    preHandler: authGuard,
  }, async (req, reply) => authController.getSession(req, reply));
}
