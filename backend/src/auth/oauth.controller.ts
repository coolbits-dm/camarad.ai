import { FastifyRequest, FastifyReply } from 'fastify';
import { oauthService } from './oauth.service';
import { env } from '../config/env';

export class OAuthController {
  /**
   * GET /auth/oauth/google/redirect
   * Redirect user to Google OAuth consent screen
   */
  async googleRedirect(_request: FastifyRequest, reply: FastifyReply) {
    try {
      const authUrl = oauthService.getGoogleAuthUrl();
      return reply.redirect(authUrl);
    } catch (error) {
      return reply.code(500).send({
        error: 'OAuth redirect failed',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }

  /**
   * GET /auth/oauth/google/callback
   * Handle callback from Google OAuth
   */
  async googleCallback(request: FastifyRequest<{ Querystring: { code?: string; error?: string } }>, reply: FastifyReply) {
    try {
      const { code, error } = request.query;

      // Handle OAuth error
      if (error) {
        return reply.redirect(`${env.CORS_ORIGIN}/auth/error?reason=${error}`);
      }

      // Validate code
      if (!code) {
        return reply.code(400).send({
          error: 'Bad request',
          message: 'Authorization code is required',
        });
      }

      // Exchange code for user data and JWT
      const result = await oauthService.handleGoogleCallback(code);

      // Set HTTP-only cookie
      reply.setCookie('access_token', result.accessToken, {
        httpOnly: true,
        secure: env.COOKIE_SECURE,
        sameSite: env.COOKIE_SAME_SITE,
        path: '/',
        domain: env.COOKIE_DOMAIN,
        maxAge: 7 * 24 * 60 * 60, // 7 days
      });

      // Redirect to frontend with success
      return reply.redirect(`${env.CORS_ORIGIN}/dashboard`);
    } catch (error) {
      return reply.redirect(`${env.CORS_ORIGIN}/auth/error?reason=oauth_failed`);
    }
  }
}

export const oauthController = new OAuthController();
