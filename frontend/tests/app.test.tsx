import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from '../src/App';
import { ErrorState } from '../src/components/States';
import { ApiError } from '../src/types';
import { RAW_ASK, RAW_META } from './fixtures';

const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

afterEach(() => vi.unstubAllGlobals());

function stubFetch(askResponse: () => Response) {
  const calls: { url: string; body?: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return url.endsWith('/meta') ? json(RAW_META) : askResponse();
    }),
  );
  return calls;
}

describe('ErrorState', () => {
  it('shows message, request id and a working Retry button', () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError('boom', 'req-9', 500)} onRetry={retry} />);
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('boom')).toBeTruthy();
    expect(screen.getByText('req-9')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

describe('App', () => {
  it('shows dataset info from /meta in the footer', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    expect(await screen.findByText('4b3139dc')).toBeTruthy();
    expect(screen.getByText('892')).toBeTruthy();
    expect(screen.getByText('52')).toBeTruthy();
  });

  it('sends only {question}, renders a resolving chip and flags the unresolved one', async () => {
    const calls = stubFetch(() => json(RAW_ASK, 200, { 'x-request-id': 'req-ok' }));
    render(<App />);
    await screen.findByText('4b3139dc');
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'What about PMMA?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByRole('button', { name: /Citation ACME-BRE-003/ })).toBeTruthy();
    const post = calls.find((c) => c.url.endsWith('/ask'));
    expect(post?.url).toBe('/api/v1/ask');
    expect(post?.body).toEqual({ question: 'What about PMMA?' });
    expect(screen.getByText('unresolved citation')).toBeTruthy();
    expect(screen.getByTestId('limitations')).toBeTruthy();
    expect(screen.getByTestId('modeled-banner')).toBeTruthy();
    expect(screen.getByText('req-ok')).toBeTruthy();
  });

  it('shows the modeled toggle as disabled because the API cannot accept it', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    await screen.findByText('4b3139dc');
    expect((screen.getByLabelText('Include modeled rows') as HTMLInputElement).disabled).toBe(true);
  });

  it('submits on Enter but not on Shift+Enter', async () => {
    const calls = stubFetch(() => json(RAW_ASK));
    render(<App />);
    await screen.findByText('4b3139dc');
    const box = screen.getByLabelText('Your question');
    fireEvent.change(box, { target: { value: 'hello' } });
    fireEvent.keyDown(box, { key: 'Enter', shiftKey: true });
    expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(0);
    fireEvent.keyDown(box, { key: 'Enter' });
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(1));
  });

  it('shows the request id on a server error and retries', async () => {
    let n = 0;
    const calls = stubFetch(() => (n++ === 0 ? json({ error_code: 'INTERNAL_SERVER_ERROR', message: 'pipeline failed', request_id: 'req-err' }, 500) : json(RAW_ASK)));
    render(<App />);
    await screen.findByText('4b3139dc');
    fireEvent.change(screen.getByLabelText('Your question'), { target: { value: 'q' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByText('req-err')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('button', { name: /Citation ACME-BRE-003/ })).toBeTruthy();
    expect(calls.filter((c) => c.url.endsWith('/ask'))).toHaveLength(2);
  });

  it('labels the static questions as examples', async () => {
    stubFetch(() => json(RAW_ASK));
    render(<App />);
    expect(await screen.findByText('Example')).toBeTruthy();
  });
});
