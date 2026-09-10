import { randomBytes, timingSafeEqual } from 'node:crypto';
import http from 'node:http';

const listenHost = '127.0.0.1';
const listenPort = 3100;
const webUpstream = { host: '127.0.0.1', port: 3000 };
const apiUpstream = { host: '127.0.0.1', port: 8000 };
const cookieName = 'maiup_preview';
const configuredTokens = (process.env.MAIUP_PREVIEW_TOKENS ?? process.env.MAIUP_PREVIEW_TOKEN ?? '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);
const tokens = configuredTokens.length > 0
  ? configuredTokens
  : [randomBytes(24).toString('base64url')];
const primaryToken = tokens[0];

function matchesToken(candidate) {
  if (!candidate) return false;
  const actual = Buffer.from(candidate);
  return tokens.some((token) => {
    const expected = Buffer.from(token);
    return actual.length === expected.length && timingSafeEqual(actual, expected);
  });
}

function cookieToken(request) {
  const cookies = request.headers.cookie?.split(';') ?? [];
  for (const cookie of cookies) {
    const [name, ...value] = cookie.trim().split('=');
    if (name === cookieName) return value.join('=');
  }
  return null;
}

const server = http.createServer((request, response) => {
  const requestUrl = new URL(request.url ?? '/', 'http://preview.local');
  const queryToken = requestUrl.searchParams.get('token');

  if (requestUrl.pathname === '/__maiup_preview_auth' && matchesToken(queryToken)) {
    const requestedNext = requestUrl.searchParams.get('next') ?? '/';
    const safeNext = requestedNext.startsWith('/') && !requestedNext.startsWith('//')
      ? requestedNext
      : '/';
    const safeNextJson = JSON.stringify(safeNext).replaceAll('<', '\\u003c');
    response.writeHead(200, {
      'Cache-Control': 'no-store',
      'Content-Type': 'text/html; charset=utf-8',
      'Set-Cookie': `${cookieName}=${queryToken}; HttpOnly; Secure; SameSite=None; Path=/; Max-Age=43200`,
    });
    response.end(`<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>正在打开 MaiUp</title>
  </head>
  <body style="margin:0;background:#07131f;color:#e2e8f0;font:16px system-ui;display:grid;min-height:100vh;place-items:center">
    <main style="padding:24px;text-align:center">
      <p>访问验证成功，正在进入 MaiUp…</p>
      <button id="continue" style="margin-top:12px;padding:12px 18px;border:0;border-radius:12px;background:#67e8f9;font-weight:700">继续</button>
    </main>
    <script>
      document.getElementById('continue').addEventListener('click', () => location.replace(${safeNextJson}));
      setTimeout(() => location.replace(${safeNextJson}), 500);
    </script>
  </body>
</html>`);
    return;
  }

  const isPublicExporter = (request.method === 'GET' || request.method === 'HEAD')
    && requestUrl.pathname === '/maiup-dxnet-export.js';

  if (!isPublicExporter && !matchesToken(cookieToken(request))) {
    response.writeHead(401, {
      'Cache-Control': 'no-store',
      'Content-Type': 'text/plain; charset=utf-8',
    });
    response.end('MaiUp private preview: open the complete access link.');
    return;
  }

  const upstream = requestUrl.pathname === '/health' || requestUrl.pathname.startsWith('/v1/')
    ? apiUpstream
    : webUpstream;
  const headers = { ...request.headers, host: `${upstream.host}:${upstream.port}` };
  const proxyRequest = http.request(
    {
      host: upstream.host,
      port: upstream.port,
      method: request.method,
      path: request.url,
      headers,
    },
    (proxyResponse) => {
      response.writeHead(proxyResponse.statusCode ?? 502, proxyResponse.headers);
      proxyResponse.pipe(response);
    },
  );
  proxyRequest.on('error', () => {
    if (!response.headersSent) {
      response.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' });
    }
    response.end('MaiUp preview upstream is unavailable.');
  });
  request.pipe(proxyRequest);
});

server.listen(listenPort, listenHost, () => {
  console.log(`MaiUp preview gateway listening on http://${listenHost}:${listenPort}`);
  console.log(`Preview tokens loaded: ${tokens.length}; primary token: ${primaryToken}`);
});
