import crypto from 'crypto';
import { prisma } from '../db/client';
import { logger } from '../config/logger';
import { env } from '../config/env';

export class EmailService {
  /**
   * Generate secure verification token
   */
  private generateVerificationToken(): string {
    return crypto.randomBytes(32).toString('hex');
  }

  /**
   * Send verification email (mock - logs to console)
   * In production, this will use SMTP/SendGrid/SES
   */
  async sendVerificationEmail(userId: string, email: string): Promise<void> {
    try {
      // Generate token
      const token = this.generateVerificationToken();
      const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours

      // Save token to database
      await prisma.user.update({
        where: { id: userId },
        data: {
          verificationToken: token,
          verificationTokenExpires: expiresAt,
        },
      });

      // Construct verification URL
      const verificationUrl = `${env.CORS_ORIGIN}/auth/verify-email?token=${token}`;

      // Mock email sending (log to console)
      if (env.EMAIL_ENABLED) {
        // TODO: Integrate with real email service (SendGrid, SES, etc.)
        logger.info({ email, verificationUrl }, 'Email would be sent in production');
      } else {
        logger.info(
          {
            to: email,
            subject: 'Verify your Camarad email address',
            verificationUrl,
            expiresAt,
          },
          '📧 VERIFICATION EMAIL (MOCK)'
        );
        
        console.log('\n' + '='.repeat(80));
        console.log('📧 EMAIL VERIFICATION (Development Mode)');
        console.log('='.repeat(80));
        console.log(`To: ${email}`);
        console.log(`Subject: Verify your Camarad email address`);
        console.log(`\nClick the link below to verify your email:`);
        console.log(`\n👉 ${verificationUrl}\n`);
        console.log(`This link expires at: ${expiresAt.toISOString()}`);
        console.log('='.repeat(80) + '\n');
      }

      logger.info({ userId, email }, 'Verification email sent');
    } catch (error) {
      logger.error({ error, userId, email }, 'Failed to send verification email');
      throw new Error('Failed to send verification email');
    }
  }

  /**
   * Verify email with token
   */
  async verifyEmail(token: string): Promise<boolean> {
    try {
      const user = await prisma.user.findFirst({
        where: {
          verificationToken: token,
          verificationTokenExpires: {
            gt: new Date(), // Token not expired
          },
        },
      });

      if (!user) {
        logger.warn({ token }, 'Invalid or expired verification token');
        return false;
      }

      // Mark email as verified and clear token
      await prisma.user.update({
        where: { id: user.id },
        data: {
          emailVerified: true,
          verificationToken: null,
          verificationTokenExpires: null,
        },
      });

      logger.info({ userId: user.id, email: user.email }, 'Email verified successfully');
      return true;
    } catch (error) {
      logger.error({ error, token }, 'Email verification failed');
      return false;
    }
  }

  /**
   * Resend verification email
   */
  async resendVerificationEmail(userId: string): Promise<void> {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: { email: true, emailVerified: true },
    });

    if (!user) {
      throw new Error('User not found');
    }

    if (user.emailVerified) {
      throw new Error('Email already verified');
    }

    await this.sendVerificationEmail(userId, user.email);
  }
}

export const emailService = new EmailService();
