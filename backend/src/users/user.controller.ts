import { FastifyRequest, FastifyReply } from 'fastify';
import { userService } from './user.service';
import { UpdateUserSchema } from '../types/user';

export class UserController {
  /**
   * GET /user/me
   */
  async getMe(request: FastifyRequest, reply: FastifyReply) {
    try {
      const userId = request.userId;

      if (!userId) {
        return reply.code(401).send({
          error: 'Unauthorized',
        });
      }

      const user = await userService.getUserById(userId);

      if (!user) {
        return reply.code(404).send({
          error: 'User not found',
        });
      }

      return reply.code(200).send({
        success: true,
        user,
      });
    } catch (error) {
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }

  /**
   * PATCH /user/me
   */
  async updateMe(request: FastifyRequest, reply: FastifyReply) {
    try {
      const userId = request.userId;

      if (!userId) {
        return reply.code(401).send({
          error: 'Unauthorized',
        });
      }

      const input = UpdateUserSchema.parse(request.body);
      const user = await userService.updateUser(userId, input);

      return reply.code(200).send({
        success: true,
        user,
      });
    } catch (error) {
      if (error instanceof Error) {
        return reply.code(400).send({
          error: 'Update failed',
          message: error.message,
        });
      }
      return reply.code(500).send({
        error: 'Internal server error',
      });
    }
  }
}

export const userController = new UserController();
