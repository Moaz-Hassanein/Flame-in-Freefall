import { ApiError, type AskResult, type Meta } from '../types';
import { isObj, normalizeAsk, normalizeMeta } from './normalize';

const BASE = '/api/v1';

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error body */
  }
  let message = `${res.status} ${res.statusText}`.trim();
  let requestId = res.headers.get('x-request-id');
  if (isObj(body)) {
    if (typeof body.request_id === 'string') requestId = body.request_id;
    const d = body.detail ?? body.message ?? body.error;
    if (typeof d === 'string') message = d;
    else if (isObj(d) && typeof d.message === 'string') message = d.message;
  }
  return new ApiError(message, requestId, res.status);
}

async function request(path: string, init?: RequestInit): Promise<{ json: unknown; requestId: string | null }> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e;
    throw new ApiError('Could not reach the server. Check that the backend is running.');
  }
  if (!res.ok) throw await toApiError(res);
  return { json: await res.json(), requestId: res.headers.get('x-request-id') };
}

export async function getMeta(signal?: AbortSignal): Promise<Meta> {
  return normalizeMeta((await request('/meta', { signal })).json);
}

/** One request, one response. No streaming. */
export async function ask(question: string, signal?: AbortSignal): Promise<AskResult> {
  // AskRequest accepts only `question` (additionalProperties: false).
  const { json, requestId } = await request('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  });
  return normalizeAsk(json, requestId);
}
