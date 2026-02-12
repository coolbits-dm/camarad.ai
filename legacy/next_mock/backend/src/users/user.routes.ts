import { FastifyInstance } from 'fastify';
import { userController } from './user.controller';
import { authGuard } from '../middleware/authGuard';

export async function userRoutes(app: FastifyInstance) {
  // All user routes require authentication
  app.addHook('preHandler', authGuard);

  app.get('/user/me', async (req, reply) => userController.getMe(req, reply));
  app.patch('/user/me', async (req, reply) => userController.updateMe(req, reply));
}
