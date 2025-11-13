import { prisma } from '../db/client';
import { UpdateUserInput } from '../types/user';
import { logger } from '../config/logger';

export class UserService {
  /**
   * Get user by ID
   */
  async getUserById(userId: string) {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        displayName: true,
        avatarUrl: true,
        emailVerified: true,
        twoFactorEnabled: true,
        createdAt: true,
        updatedAt: true,
        lastLoginAt: true,
      },
    });

    return user;
  }

  /**
   * Update user profile
   */
  async updateUser(userId: string, input: UpdateUserInput) {
    const user = await prisma.user.update({
      where: { id: userId },
      data: input,
      select: {
        id: true,
        email: true,
        displayName: true,
        avatarUrl: true,
        emailVerified: true,
        updatedAt: true,
      },
    });

    logger.info({ userId }, 'User profile updated');
    return user;
  }

  /**
   * Delete user account
   */
  async deleteUser(userId: string) {
    await prisma.user.delete({
      where: { id: userId },
    });

    logger.info({ userId }, 'User account deleted');
  }
}

export const userService = new UserService();
