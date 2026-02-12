export interface FetchJsonOptions extends Omit<RequestInit, 'body'> {
  /**
   * JSON body to send with the request. Automatically stringified.
   */
  body?: unknown;
  /**
   * When enabled, 429 responses will retry with exponential backoff.
   */
  backoff?: boolean;
  /**
   * Maximum number of retries when `backoff` is true.
   */
  retryLimit?: number;
}

export interface LatencyMeta {
  url: string;
  method: string;
  status: number;
  attempt: number;
  timestamp: number;
}

export interface CouncilRequest {
  text: string;
  sessionId: string;
  metadata?: Record<string, unknown>;
}

export interface CouncilPayload {
  text: string;
  sessionId: string;
  metadata: Record<string, unknown>;
  stream: boolean;
}

const RETRY_DELAYS = [250, 500, 1000, 2000];

type LatencyListener = (latency: number, meta: LatencyMeta) => void;

const latencyListeners = new Set<LatencyListener>();
let lastLatency: number | null = null;
let lastLatencyMeta: LatencyMeta | null = null;

export function buildCouncilPayload(request: CouncilRequest, stream: boolean): CouncilPayload {
  const normalizedText = typeof request.text === 'string' ? request.text.trim() : '';
  if (!normalizedText) {
    console.warn('[council] Empty text payload');
  }

  const normalizedSessionId = typeof request.sessionId === 'string' && request.sessionId.trim()
    ? request.sessionId.trim()
    : 'personal';

  const metadata: Record<string, unknown> = {
    source: 'ui',
    ts: Date.now(),
    ...(request.metadata ?? {}),
  };

  if (!('timestamp' in metadata)) {
    metadata.timestamp = metadata.ts;
  }

  return {
    text: normalizedText,
    sessionId: normalizedSessionId,
    metadata,
    stream,
  };
}

function logCouncilRequest(endpoint: string, payload: CouncilPayload) {
  try {
    console.log('[council:fetch]', endpoint, JSON.stringify(payload));
  } catch {
    console.log('[council:fetch]', endpoint, payload);
  }
}

export class FetcherError extends Error {
  public status: number;
  public url: string;
  public body: unknown;

  constructor(message: string, url: string, status: number, body: unknown) {
    super(message);
    this.name = 'FetcherError';
    this.status = status;
    this.url = url;
    this.body = body;
  }
}

function emitLatency(latency: number, meta: LatencyMeta) {
  lastLatency = latency;
  lastLatencyMeta = meta;
  latencyListeners.forEach((listener) => {
    try {
      listener(latency, meta);
    } catch {
      // Listener errors are ignored.
    }
  });
}

export function onLatency(listener: LatencyListener) {
  latencyListeners.add(listener);
  return () => {
    latencyListeners.delete(listener);
  };
}

export function getLatestLatency() {
  return { latency: lastLatency, meta: lastLatencyMeta };
}

async function sleep(ms: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function serializeBody(body: unknown) {
  if (body === undefined || body === null) {
    return undefined;
  }
  if (body instanceof FormData || body instanceof URLSearchParams) {
    return body;
  }
  return JSON.stringify(body);
}

function ensureHeaders(init: FetchJsonOptions) {
  const headers = new Headers(init.headers ?? {});
  if (init.body !== undefined && !(init.body instanceof FormData) && !(init.body instanceof URLSearchParams)) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  return headers;
}

export async function fetchJson<T>(input: string, init: FetchJsonOptions = {}): Promise<T> {

  const { backoff = false, retryLimit = RETRY_DELAYS.length, body, ...rest } = init;
  const headers = ensureHeaders({ ...rest, body });
  const method = (rest.method ?? (body !== undefined ? 'POST' : 'GET')).toUpperCase();

  let attempt = 0;
  // Always include the original attempt even if retryLimit is zero.
  const maxAttempts = Math.min(retryLimit + 1, RETRY_DELAYS.length + 1);

  while (attempt < maxAttempts) {
    const attemptStart = typeof performance !== 'undefined' ? performance.now() : Date.now();
    let response: Response;
    try {
      response = await fetch(input, {
        ...rest,
        method,
        headers,
        body: serializeBody(body),
      });
    } catch (error) {
      throw new FetcherError(
        error instanceof Error ? error.message : 'Network request failed',
        input,
        -1,
        null,
      );
    }

    const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - attemptStart;
    const meta: LatencyMeta = {
      url: input,
      method,
      status: response.status,
      attempt: attempt + 1,
      timestamp: Date.now(),
    };
    emitLatency(elapsed, meta);

    if (response.status === 429 && backoff && attempt < retryLimit) {
      await sleep(RETRY_DELAYS[attempt] ?? RETRY_DELAYS[RETRY_DELAYS.length - 1]);
      attempt += 1;
      continue;
    }

    if (!response.ok) {
      let errorBody: unknown = null;
      try {
        const text = await response.text();
        errorBody = text;
      } catch {
        errorBody = null;
      }
      throw new FetcherError(`Request failed with status ${response.status}`, input, response.status, errorBody);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as T;
    }

    return (await response.text()) as T;
  }

  throw new FetcherError('Retry budget exhausted', input, 429, null);
}

export interface StreamOptions extends Omit<RequestInit, 'body' | 'method'> {
  method?: string;
}

export async function stream(
  input: string,
  body: unknown,
  onChunk: (chunk: unknown) => void,
  init: StreamOptions = {},
): Promise<void> {
  const method = (init.method ?? 'POST').toUpperCase();
  const headers = ensureHeaders({ ...(init as FetchJsonOptions), body });
  headers.set('Accept', 'text/event-stream');

  let response: Response;
  const startTime = typeof performance !== 'undefined' ? performance.now() : Date.now();

  try {
    response = await fetch(input, {
      ...init,
      method,
      headers,
      body: serializeBody(body),
    });
  } catch (error) {
    throw new FetcherError(
      error instanceof Error ? error.message : 'Network request failed',
      input,
      -1,
      null,
    );
  }

  if (!response.ok) {
    let errorBody: unknown = null;
    try {
      errorBody = await response.text();
    } catch {
      errorBody = null;
    }
    throw new FetcherError(`Request failed with status ${response.status}`, input, response.status, errorBody);
  }

  if (!response.body) {
    throw new FetcherError('Streaming response not supported in this environment', input, response.status, null);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const processBuffer = () => {
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (rawEvent.startsWith('data:')) {
        const data = rawEvent.slice(5).trim();
        if (data === '[DONE]') {
          boundary = buffer.indexOf('\n\n');
          continue;
        }
        if (data.length > 0) {
          try {
            const parsed = JSON.parse(data);
            onChunk(parsed);
          } catch {
            // ignore malformed chunks
          }
        }
      }
      boundary = buffer.indexOf('\n\n');
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    processBuffer();
  }

  buffer += decoder.decode();
  processBuffer();

  const elapsed = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - startTime;
  emitLatency(elapsed, {
    url: input,
    method,
    status: response.status,
    attempt: 1,
    timestamp: Date.now(),
  });
}

export async function councilRequest<T = unknown>(endpoint: string, request: CouncilRequest): Promise<T> {
  const streamEndpoint = endpoint.trim().endsWith('/stream');
  const payload = buildCouncilPayload(request, streamEndpoint);
  logCouncilRequest(endpoint, payload);

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new FetcherError(
      error instanceof Error ? error.message : 'Network request failed',
      endpoint,
      -1,
      null,
    );
  }

  if (!response.ok) {
    let errorBody: unknown = null;
    try {
      const text = await response.text();
      if (text) {
        try {
          errorBody = JSON.parse(text);
        } catch {
          errorBody = text;
        }
      }
    } catch {
      errorBody = null;
    }
    const message = response.statusText
      ? `Request failed with ${response.status} ${response.statusText}`
      : `Request failed with status ${response.status}`;
    throw new FetcherError(message, endpoint, response.status, errorBody);
  }

  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}

export async function councilStream(
  endpoint: string,
  request: CouncilRequest,
  onChunk: (chunk: unknown) => void,
  init: StreamOptions = {},
): Promise<void> {
  const payload = buildCouncilPayload(request, endpoint.trim().endsWith('/stream'));
  logCouncilRequest(endpoint, payload);

  const headers = new Headers(init.headers ?? {});
  headers.set('Content-Type', 'application/json');

  await stream(endpoint, payload, onChunk, {
    ...init,
    headers,
  });
}

const fetcher = {
  json: fetchJson,
  stream,
  onLatency,
  getLatestLatency,
  councilRequest,
  councilStream,
  buildCouncilPayload,
};

export default fetcher;
