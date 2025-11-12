import type { NextApiRequest, NextApiResponse } from 'next';
import { HEALTHCHECK_URL } from '@/lib/config';

type StatusPayload = {
  ok: boolean;
  target: string;
  status?: number;
  error?: string;
};

export default async function handler(_req: NextApiRequest, res: NextApiResponse<StatusPayload>) {
  const target = process.env.NEXT_PUBLIC_HEALTHCHECK_URL || HEALTHCHECK_URL;

  try {
    const response = await fetch(target, {
      method: 'GET',
      headers: { Accept: 'application/json' },
    });

    res.status(200).json({
      ok: response.ok,
      target,
      status: response.status,
    });
  } catch (error) {
    res.status(200).json({
      ok: false,
      target,
      error: error instanceof Error ? error.message : 'fetch failed',
    });
  }
}
