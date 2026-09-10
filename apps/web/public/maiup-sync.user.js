// ==UserScript==
// @name MaiUp official score sync
// @namespace https://github.com/Zephyruz/MaiUp
// @version 1.1.0
// @description Import your scores when you click sync in local MaiUp
// @match https://maimaidx-eng.com/maimai-mobile/home/*
// @run-at document-idle
// @grant none
// @noframes
// ==/UserScript==
if (new URLSearchParams(location.hash.slice(1)).get('maiupAuto') === '1') {
/* MaiUp official-site bridge. This adapter uses the published mai-tools exporter.
 * It never reads cookies or passwords and never sends scores in a URL.
 */
(function () {
  'use strict';
  const OFFICIAL = 'https://maimaidx-eng.com';
  const TOOL_HOST = 'https://myjian.github.io/mai-tools';
  const LOCAL = 'http://localhost:3000';
  const fragment = new URLSearchParams(location.hash.slice(1));
  const automatic = fragment.get('maiupAuto') === '1';
  if (location.origin !== OFFICIAL) {
    alert('Run MaiUp sync on maimai DX NET International after signing in.');
    return;
  }
  if (window.__maiupSyncRunning) return;
  if (location.pathname !== '/maimai-mobile/home/' ||
      !document.querySelector('.see_through_block') || !document.querySelector('.name_block')) {
    alert('Sign in, open your maimai DX NET home page, then start MaiUp sync again.');
    return;
  }
  const nonce = automatic ? fragment.get('maiupNonce') : crypto.randomUUID();
  const localOrigin = automatic ? fragment.get('maiupOrigin') : LOCAL;
  if (!/^[a-f0-9-]{36}$/.test(nonce || '') ||
      !['http://localhost:3000', 'http://127.0.0.1:3000'].includes(localOrigin)) {
    alert('Invalid MaiUp connection. Start a new sync from your local MaiUp page.');
    return;
  }
  // The userscript uses the MaiUp tab that opened this page. A bookmarklet can
  // instead create its receiver synchronously during the user's click.
  const receiver = automatic ? window.opener : window.open(
    localOrigin + '/sync#maiupNonce=' + nonce, '_blank', 'popup=false',
  );
  if (!receiver) {
    alert('Allow the MaiUp tab to open, or start again from MaiUp in this same browser.');
    return;
  }
  if (automatic) history.replaceState(null, '', location.pathname + location.search);
  window.__maiupSyncRunning = true;
  let started = false;
  let finished = false;
  let delivered = false;
  let exportedText = '';
  let poll;
  let timer;
  const banner = document.createElement('div');
  banner.id = 'maiup-sync-status';
  banner.style.cssText = 'position:fixed;bottom:12px;left:12px;right:12px;z-index:2147483647;padding:16px;background:#132331;color:white;border:2px solid #67e8f9;border-radius:12px;font:16px sans-serif;';
  banner.textContent = 'MaiUp: connecting to your local app…';
  document.body.append(banner);
  const send = (type, extra = {}) => receiver.postMessage(
    { protocol: 'maiup-sync-v1', nonce, type, ...extra }, localOrigin,
  );
  const cleanup = () => {
    finished = true;
    clearInterval(poll);
    clearInterval(timer);
    clearTimeout(deadline);
    window.removeEventListener('message', onMessage);
    window.__maiupSyncRunning = false;
  };
  const fail = (message) => {
    banner.textContent = 'MaiUp: ' + message;
    send('error', { message });
    cleanup();
  };
  function fetchScores() {
    started = true;
    banner.textContent = 'MaiUp: loading mai-tools and fetching all score difficulties…';
    send('progress');
    const script = document.createElement('script');
    script.src = TOOL_HOST + '/scripts/score-download.js?t=' + Math.floor(Date.now() / 60000);
    script.onerror = () => fail('Could not load mai-tools. Please try again.');
    script.onload = () => {
      if (finished) return;
      const area = document.querySelector('#outputArea');
      const output = area && area.querySelector('#outputText');
      const status = area && area.querySelector('.fetchStatus');
      const buttons = area && area.querySelectorAll('button');
      const included = area && area.querySelector('.included');
      if (!output || !status || !included || buttons.length !== 2) {
        fail('The mai-tools exporter layout changed. Use manual import and report this issue.');
        return;
      }
      // Use all upstream export fields, including DX score and its community constant.
      for (const label of area.querySelectorAll('.excluded label')) included.append(label);
      poll = setInterval(() => {
        if (receiver.closed) {
          fail('The MaiUp tab was closed. Start a new sync.');
          return;
        }
        // Only the upstream completion indicator authorizes sending the table.
        if (!status.textContent.trim().startsWith('✅')) return;
        if (!output.value.includes('\t') || !output.value.includes('\n')) {
          fail('No completed score table was returned. Check your login and retry.');
          return;
        }
        if (new TextEncoder().encode(output.value).length > 2_000_000) {
          fail('Score export exceeds the 2 MB limit.');
          return;
        }
        exportedText = output.value;
        clearInterval(poll);
        send('scores', { scoreText: exportedText });
        banner.textContent = 'MaiUp: scores fetched; waiting for local import…';
      }, 500);
      buttons[0].click();
    };
    document.body.append(script);
  }
  function onMessage(event) {
    const data = event.data;
    if (event.origin !== localOrigin || event.source !== receiver || !data ||
        data.protocol !== 'maiup-sync-v1' || data.nonce !== nonce) return;
    if (data.type === 'ready' && !started) fetchScores();
    if (data.type === 'received') delivered = true;
    if (data.type === 'saved') {
      banner.textContent = 'MaiUp: sync complete. Your scores and recommended levels are ready in MaiUp.';
      cleanup();
    }
    if (data.type === 'error') fail('Local import failed. See the MaiUp tab for details.');
    if (data.type === 'cancel') {
      banner.textContent = 'MaiUp: transfer cancelled. An upstream fetch already in progress may finish.';
      cleanup();
    }
  }
  window.addEventListener('message', onMessage);
  const deadline = setTimeout(() => fail('Sync timed out. Check your login and start again.'), 180_000);
  timer = setInterval(() => {
    if (finished) return;
    if (exportedText && !delivered) send('scores', { scoreText: exportedText });
    else if (!started) send('hello');
  }, 1000);
  send('hello');
})();

}
