const FALLBACK_BACKEND_URL = 'https://api.camarad.ai';

export const BACKEND_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || FALLBACK_BACKEND_URL).replace(/\/$/, '');
export const HEALTHCHECK_URL =
	process.env.NEXT_PUBLIC_HEALTHCHECK_URL || `${BACKEND_URL}/healthz`;
