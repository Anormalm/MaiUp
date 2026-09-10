import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const source = readFileSync(new URL('../public/maiup-sync.js', import.meta.url), 'utf8');
const protocolSource = readFileSync(new URL('../lib/official-sync.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(protocolSource, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const { validSyncMessage, officialSyncUrl, syncWaitStatus, checkLocalCatalog } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const nonce = '12345678-1234-1234-1234-123456789abc';
const official = 'https://maimaidx-eng.com';
const local = 'http://localhost:3000';

test('a missing helper is identified early and never mislabeled as a fetch timeout', () => {
  assert.equal(syncWaitStatus(false, 9999, false), null);
  assert.equal(syncWaitStatus(false, 10_000, false), 'helper_missing');
  assert.equal(syncWaitStatus(false, 180_000, false), 'helper_missing');
  assert.equal(syncWaitStatus(true, 10_000, false), null);
  assert.equal(syncWaitStatus(true, 180_000, false), 'fetch_timeout');
  assert.equal(syncWaitStatus(false, 100, true), 'connection_closed');
});

test('sync preflight reports a stopped API or missing catalog before visiting the official site', async () => {
  await assert.rejects(checkLocalCatalog(async () => { throw new TypeError('fetch failed'); }), /8000/);
  await assert.rejects(checkLocalCatalog(async () => new Response('{}', { status: 500 })), /API/);
  await assert.rejects(checkLocalCatalog(async () => Response.json({ ready: false })), /曲库/);
  await checkLocalCatalog(async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/v1/catalog/status');
    assert.ok(options.signal instanceof AbortSignal);
    return Response.json({ ready: true });
  });
});

test('receiver accepts only the intended official window, origin, nonce and bounded payload', () => {
  const peer = {};
  const data = { protocol: 'maiup-sync-v1', nonce, type: 'scores', scoreText: 'Song\tChart\nx\tDX' };
  const event = { source: peer, origin: official, data };
  assert.equal(validSyncMessage(event, peer, nonce), true);
  for (const invalid of [
    { ...event, origin: 'https://maimaidx.jp' },
    { ...event, origin: 'https://maimaidx-eng.com.evil.invalid' },
    { ...event, source: {} },
    { ...event, data: { ...data, nonce: 'another' } },
    { ...event, data: { ...data, type: 'unknown' } },
    { ...event, data: { ...data, scoreText: '' } },
    { ...event, data: { ...data, scoreText: 'あ'.repeat(700_000) } },
    { ...event, data: null },
  ]) assert.equal(validSyncMessage(invalid, peer, nonce), false);
  assert.equal(validSyncMessage(event, null, nonce), false);
  const url = new URL(officialSyncUrl(local, nonce));
  assert.equal(url.origin, official);
  assert.equal(url.search, '');
  assert.match(url.hash, /maiupAuto=1/);
  assert.throws(() => officialSyncUrl('https://evil.invalid', nonce));
});

function browser({ origin = official, loggedIn = true, opener = true, automatic = true } = {}) {
  const sent = [];
  const listeners = new Map();
  const intervals = new Map();
  const timeouts = new Map();
  const appended = [];
  const alerts = [];
  let clicks = 0;
  let timerId = 0;
  const receiver = { closed: false, postMessage: (data, target) => sent.push({ data, target }) };
  const output = { value: '' };
  const status = { textContent: '' };
  const includedLabels = [];
  const area = {
    querySelector: (selector) => ({ '#outputText': output, '.fetchStatus': status,
      '.included': { append: (label) => includedLabels.push(label) } })[selector],
    querySelectorAll: (selector) => selector === 'button' ? [{ click: () => clicks++ }, {}] : ['DX Score', 'Chart Constant'],
  };
  const document = {
    body: { append: (element) => appended.push(element) },
    createElement: (tag) => ({ tag, style: {} }),
    querySelector: (selector) => selector === '#outputArea' ? area : loggedIn ? {} : null,
  };
  Object.defineProperty(document, 'cookie', { get() { throw new Error('Must not read cookies'); } });
  const window = {
    opener: opener ? receiver : null,
    open: () => receiver,
    addEventListener: (name, handler) => listeners.set(name, handler),
    removeEventListener: (name) => listeners.delete(name),
  };
  const location = { origin, pathname: '/maimai-mobile/home/', search: '',
    hash: automatic ? '#maiupAuto=1&maiupNonce=' + nonce + '&maiupOrigin=' + encodeURIComponent(local) : '' };
  const context = { window, document, location, URLSearchParams, TextEncoder,
    alert: (message) => alerts.push(message), crypto: { randomUUID: () => nonce },
    history: { replaceState() {} },
    setInterval: (fn, ms) => { const id = ++timerId; intervals.set(id, { fn, ms }); return id; },
    clearInterval: (id) => intervals.delete(id),
    setTimeout: (fn) => { const id = ++timerId; timeouts.set(id, fn); return id; },
    clearTimeout: (id) => timeouts.delete(id),
  };
  vm.runInNewContext(source, context);
  const message = (type, extra = {}, originOverride = local, sourceOverride = receiver) => listeners.get('message')?.({
    origin: originOverride, source: sourceOverride, data: { protocol: 'maiup-sync-v1', nonce, type, ...extra },
  });
  return { sent, alerts, appended, includedLabels, output, status, window, receiver,
    message, intervals, timeouts, clicks: () => clicks,
    tick: () => { for (const { fn } of [...intervals.values()]) fn(); },
    script: () => appended.find((element) => element.tag === 'script'),
  };
}

test('bridge waits for the paired receiver, exports all fields once, and never sends partial progress', () => {
  const b = browser();
  assert.equal(b.sent[0].data.type, 'hello');
  b.message('ready', {}, 'https://evil.invalid');
  b.message('ready', {}, local, {});
  b.message('ready', { nonce: 'wrong' });
  assert.equal(b.script(), undefined);
  b.message('ready');
  b.message('ready');
  assert.equal(b.appended.filter((element) => element.tag === 'script').length, 1);
  assert.match(b.script().src, /^https:\/\/myjian.github.io\/mai-tools\/scripts\/score-download.js/);
  b.script().onload();
  assert.equal(b.clicks(), 1);
  assert.deepEqual(b.includedLabels, ['DX Score', 'Chart Constant']);
  b.output.value = 'Loading BASIC scores';
  b.tick();
  assert.equal(b.sent.some(({ data }) => data.type === 'scores'), false);
  b.output.value = 'Song\tChart\tDifficulty\tAchv\tFC/AP\nExample\tDX\tMASTER\t100.5000%\tAP';
  b.status.textContent = '✅ All scores are loaded';
  b.tick();
  assert.equal(b.sent.filter(({ data }) => data.type === 'scores').length, 1);
  assert.equal(b.sent.at(-1).target, local);
  b.message('received');
  b.tick();
  assert.equal(b.sent.filter(({ data }) => data.type === 'scores').length, 1);
  b.message('saved');
  assert.equal(b.window.__maiupSyncRunning, false);
  assert.equal(b.intervals.size, 0);
  assert.equal(b.timeouts.size, 0);
});

test('bookmarklet creates a local receiver without a userscript', () => {
  const b = browser({ automatic: false, opener: false });
  assert.equal(b.sent[0].target, local);
  b.message('ready');
  assert.ok(b.script());
});

test('login, popup, upstream failures and timeout stop cleanly', () => {
  assert.equal(browser({ origin: 'https://maimaidx.jp' }).alerts.length, 1);
  assert.equal(browser({ loggedIn: false }).alerts.length, 1);
  assert.equal(browser({ opener: false }).alerts.length, 1);
  const failed = browser();
  failed.message('ready');
  failed.script().onerror();
  assert.equal(failed.sent.at(-1).data.type, 'error');
  assert.equal(failed.intervals.size, 0);
  const expired = browser();
  [...expired.timeouts.values()][0]();
  assert.match(expired.sent.at(-1).data.message, /timed out/);
  const cancelled = browser();
  cancelled.message('ready');
  cancelled.message('cancel');
  cancelled.script().onload();
  assert.equal(cancelled.clicks(), 0);
});
