import { google } from 'googleapis';
import { env } from '../config/env';
import { prisma } from '../db/client';
import { generateAccessToken } from './jwt';
import { logger } from '../config/logger';
import crypto from 'crypto';

const oauth2Client = new google.auth.OAuth2(
  env.GOOGLE_CLIENT_ID,
  env.GOOGLE_CLIENT_SECRET,
  env.GOOGLE_REDIRECT_URI
);

export class OAuthService {
  /**
   * Generate Google OAuth authorization URL
   */
  getGoogleAuthUrl(): string {
    const scopes = [
      'https://www.googleapis.com/auth/userinfo.email',
      'https://www.googleapis.com/auth/userinfo.profile',
    ];

    const url = oauth2Client.generateAuthUrl({
      access_type: 'offline',
      scope: scopes,
      prompt: 'consent',
    });

    return url;
  }

  /**
   * Exchange authorization code for tokens and create/login user
   */
  async handleGoogleCallback(code: string) {
    try {
      // Exchange code for tokens
      const { tokens } = await oauth2Client.getToken(code);
      oauth2Client.setCredentials(tokens);

      // Get user info from Google
      const oauth2 = google.oauth2({ version: 'v2', auth: oauth2Client });
      const { data: userInfo } = await oauth2.userinfo.get();

      if (!userInfo.email) {
        throw new Error('Email not provided by Google');
      }

      // Check if user exists
      let user = await prisma.user.findFirst({
        where: {
          OR: [
            { email: userInfo.email },
            {
              oauthProvider: 'google',
              oauthSub: userInfo.id as string,
            },
          ],
        },
      });

      // Create user if doesn't exist
      if (!user) {
        user = await prisma.user.create({
          data: {
            email: userInfo.email,
            displayName: userInfo.name || userInfo.email.split('@')[0],
            avatarUrl: userInfo.picture || null,
            oauthProvider: 'google',
            oauthSub: userInfo.id as string,
            emailVerified: userInfo.verified_email || false,
          },
        });

        logger.info({ userId: user.id, email: user.email }, 'User created via Google OAuth');
      } else {
        // Update OAuth info if user exists but wasn't linked
        if (!user.oauthProvider || !user.oauthSub) {
          user = await prisma.user.update({
            where: { id: user.id },
            data: {
              oauthProvider: 'google',
              oauthSub: userInfo.id as string,
              emailVerified: true, // Google verified
              avatarUrl: user.avatarUrl || userInfo.picture || null,
            },
          });
        }

        // Update last login
        await prisma.user.update({
          where: { id: user.id },
          data: { lastLoginAt: new Date() },
        });

        logger.info({ userId: user.id, email: user.email }, 'User logged in via Google OAuth');
      }

      // Create session
      const session = await prisma.session.create({
        data: {
          userId: user.id,
          token: crypto.randomUUID(),
          expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
        },
      });

      // Generate JWT
      const accessToken = generateAccessToken({
        userId: user.id,
        email: user.email,
        sessionId: session.id,
      });

      return {
        user: {
          id: user.id,
          email: user.email,
          displayName: user.displayName,
          avatarUrl: user.avatarUrl,
          emailVerified: user.emailVerified,
        },
        accessToken,
      };
    } catch (error) {
      logger.error({ error }, 'Google OAuth callback failed');
      throw new Error('Failed to authenticate with Google');
    }
  }
}

export const oauthService = new OAuthService();
