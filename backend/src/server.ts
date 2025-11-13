import Fastify from 'fastify';
import cors from '@fastify/cors';
import cookie from '@fastify/cookie';
import { env } from './config/env';
import { logger } from './config/logger';
import { connectDatabase } from './db/client';
import { authRoutes } from './auth/auth.routes';
import { userRoutes } from './users/user.routes';

const app = Fastify({
  logger: env.NODE_ENV === 'development' ? {
    transport: {
      target: 'pino-pretty',
      options: {
        colorize: true,
        translateTime: 'HH:MM:ss Z',
        ignore: 'pid,hostname',
      }
    }
  } : true,
  trustProxy: true,
  requestIdLogLabel: 'reqId',
});

// Register plugins
async function registerPlugins() {
  // CORS
  await app.register(cors, {
    origin: env.CORS_ORIGIN,
    credentials: env.CORS_CREDENTIALS,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  });

  // Cookies
  await app.register(cookie, {
    secret: env.JWT_SECRET,
    parseOptions: {},
  });
}

// Register routes
async function registerRoutes() {
  // Health check
  app.get('/health', async () => {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  });

  // API routes
  await app.register(authRoutes);
  await app.register(userRoutes);

  // 404 handler
  app.setNotFoundHandler((request, reply) => {
    reply.code(404).send({
      error: 'Not Found',
      message: `Route ${request.method} ${request.url} not found`,
    });
  });

  // Error handler
  app.setErrorHandler((error, request, reply) => {
    logger.error({ error, url: request.url }, 'Request error');
    
    reply.code(error.statusCode || 500).send({
      error: error.name || 'Internal Server Error',
      message: env.NODE_ENV === 'production' ? 'An error occurred' : error.message,
    });
  });
}

// Graceful shutdown
async function gracefulShutdown(signal: string) {
  logger.info(`${signal} received, shutting down gracefully...`);
  
  await app.close();
  logger.info('Server closed');
  
  process.exit(0);
}

// Start server
async function start() {
  try {
    // Connect to database
    await connectDatabase();

    // Register plugins and routes
    await registerPlugins();
    await registerRoutes();

    // Start listening
    await app.listen({
      port: env.PORT,
      host: env.HOST,
    });

    logger.info(`🚀 Camarad API running on http://${env.HOST}:${env.PORT}`);
    logger.info(`📝 Environment: ${env.NODE_ENV}`);
    logger.info(`🗄️  Database: Connected`);

    // Register shutdown handlers
    process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
    process.on('SIGINT', () => gracefulShutdown('SIGINT'));
    
  } catch (error) {
    logger.error({ error }, 'Failed to start server');
    process.exit(1);
  }
}

// Run
start();
