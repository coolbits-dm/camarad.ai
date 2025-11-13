import { prisma } from '../db/client';
import { hashPassword, verifyPassword } from './password';
import { generateAccessToken } from './jwt';
import { RegisterInput, LoginInput, AuthResponse } from '../types/auth';
import { logger } from '../config/logger';
import { emailService } from './email.service';

export class AuthService {
  /**
   * Register new user with email/password
   */
  async register(input: RegisterInput): Promise<AuthResponse> {
    const { email, password, displayName } = input;

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email },
    });

    if (existingUser) {
      throw new Error('User with this email already exists');
    }

    // Hash password
    const passwordHash = await hashPassword(password);

    // Create user
    const user = await prisma.user.create({
      data: {
        email,
        passwordHash,
        displayName,
        emailVerified: false,
      },
    });

    // Send verification email (async, don't block registration)
    emailService.sendVerificationEmail(user.id, user.email).catch((error) => {
      logger.error({ error, userId: user.id }, 'Failed to send verification email after registration');
    });

    // Create session
    const session = await prisma.session.create({
      data: {
        userId: user.id,
        token: crypto.randomUUID(),
        expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
      },
    });

    // Generate tokens
    const accessToken = generateAccessToken({
      userId: user.id,
      email: user.email,
      sessionId: session.id,
    });

    logger.info({ userId: user.id, email: user.email }, 'User registered');

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
  }

  /**
   * Login user with email/password
   */
  async login(input: LoginInput, ipAddress?: string, userAgent?: string): Promise<AuthResponse> {
    const { email, password } = input;

    // Find user
    const user = await prisma.user.findUnique({
      where: { email },
    });

    if (!user || !user.passwordHash) {
      throw new Error('Invalid email or password');
    }

    // Verify password
    const isValid = await verifyPassword(user.passwordHash, password);

    if (!isValid) {
      throw new Error('Invalid email or password');
    }

    // Update last login
    await prisma.user.update({
      where: { id: user.id },
      data: { lastLoginAt: new Date() },
    });

    // Create session
    const session = await prisma.session.create({
      data: {
        userId: user.id,
        token: crypto.randomUUID(),
        expiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
        ipAddress,
        userAgent,
      },
    });

    // Generate tokens
    const accessToken = generateAccessToken({
      userId: user.id,
      email: user.email,
      sessionId: session.id,
    });

    logger.info({ userId: user.id, email: user.email }, 'User logged in');

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
  }

  /**
   * Logout user (invalidate session)
   */
  async logout(sessionId: string): Promise<void> {
    await prisma.session.delete({
      where: { id: sessionId },
    });

    logger.info({ sessionId }, 'User logged out');
  }

  /**
   * Get current user session
   */
  async getSession(sessionId: string) {
    const session = await prisma.session.findUnique({
      where: { id: sessionId },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            displayName: true,
            avatarUrl: true,
            emailVerified: true,
            createdAt: true,
          },
        },
      },
    });

    if (!session || session.expiresAt < new Date()) {
      return null;
    }

    return session;
  }

  /**
   * Verify email (mock for now)
   */
  async verifyEmail(userId: string, token: string): Promise<boolean> {
    const user = await prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user || user.verificationToken !== token) {
      return false;
    }

    await prisma.user.update({
      where: { id: userId },
      data: {
        emailVerified: true,
        verificationToken: null,
      },
    });

    logger.info({ userId }, 'Email verified');
    return true;
  }
}

export const authService = new AuthService();
