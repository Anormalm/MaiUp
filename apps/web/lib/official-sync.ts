export const OFFICIAL_ORIGIN = 'https://maimaidx-eng.com';
export const SYNC_PROTOCOL = 'maiup-sync-v1';

export function syncWaitStatus(connected: boolean, elapsedMs: number, closed: boolean) {
  if (closed) return 'connection_closed';
  if (!connected && elapsedMs >= 10_000) return 'helper_missing';
  if (connected && elapsedMs >= 180_000) return 'fetch_timeout';
  return null;
}

export async function checkLocalCatalog(fetcher: typeof fetch = fetch): Promise<void> {
  let response: Response;
  try {
    response = await fetcher('http://127.0.0.1:8000/v1/catalog/status', {
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    throw new Error('本地 API 未启动或无法连接（127.0.0.1:8000）。请先启动 MaiUp 后端，再同步。');
  }
  if (!response.ok) throw new Error('本地 API 返回错误，请检查后端后重试。');
  const catalog = (await response.json()) as { ready?: boolean };
  if (!catalog.ready) throw new Error('本地曲库尚未就绪，请先同步曲库。');
}

export type SyncMessage = {
  protocol: typeof SYNC_PROTOCOL;
  nonce: string;
  type: 'hello' | 'progress' | 'scores' | 'error';
  scoreText?: string;
  message?: string;
};

export function validSyncMessage(
  event: Pick<MessageEvent, 'origin' | 'source' | 'data'>,
  source: Window | null,
  nonce: string,
): event is MessageEvent<SyncMessage> {
  if (!source || event.source !== source || event.origin !== OFFICIAL_ORIGIN) return false;
  const data: unknown = event.data;
  if (!data || typeof data !== 'object') return false;
  const candidate = data as Record<string, unknown>;
  if (candidate.protocol !== SYNC_PROTOCOL || candidate.nonce !== nonce) return false;
  if (!['hello', 'progress', 'scores', 'error'].includes(String(candidate.type))) return false;
  if (candidate.type === 'scores') {
    return typeof candidate.scoreText === 'string' && candidate.scoreText.length > 0 &&
      candidate.scoreText.length <= 2_000_000 &&
      new TextEncoder().encode(candidate.scoreText).length <= 2_000_000;
  }
  return candidate.type !== 'error' ||
    (typeof candidate.message === 'string' && candidate.message.length <= 500);
}

export function officialSyncUrl(origin: string, nonce: string): string {
  if (!['http://localhost:3000', 'http://127.0.0.1:3000'].includes(origin)) {
    throw new Error('请在本机 http://localhost:3000 打开 MaiUp。');
  }
  const url = new URL('/maimai-mobile/home/', OFFICIAL_ORIGIN);
  url.hash = new URLSearchParams({ maiupAuto: '1', maiupOrigin: origin, maiupNonce: nonce }).toString();
  return url.toString();
}
