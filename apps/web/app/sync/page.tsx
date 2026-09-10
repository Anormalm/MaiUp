'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { OFFICIAL_ORIGIN, SYNC_PROTOCOL, checkLocalCatalog, officialSyncUrl, syncWaitStatus, validSyncMessage } from '@/lib/official-sync';

export default function SyncPage() {
  const peer = useRef<Window | null>(null);
  const nonce = useRef('');
  const importing = useRef(false);
  const expiresAt = useRef(0);
  const connected = useRef(false);
  const waitingSince = useRef(0);
  const checkingApi = useRef(false);
  const helperPrompted = useRef(false);
  const [message, setMessage] = useState('首次使用请先保存下方 MaiUp 自动同步书签。原版 mai-tools 书签不会把成绩传回 MaiUp。');
  const [active, setActive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [needsHelper, setNeedsHelper] = useState(false);
  const [bookmarklet, setBookmarklet] = useState('');

  function send(type: string) {
    peer.current?.postMessage({ protocol: SYNC_PROTOCOL, nonce: nonce.current, type }, OFFICIAL_ORIGIN);
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch('/maiup-sync.js', { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('同步书签读取失败，请刷新页面。');
        return response.text();
      })
      .then((source) => setBookmarklet('javascript:' + encodeURIComponent(source)))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setMessage(error instanceof Error ? error.message : '同步书签读取失败');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const fragment = new URLSearchParams(location.hash.slice(1));
    const fromBookmarklet = fragment.get('maiupNonce');
    if (fromBookmarklet && /^[a-f0-9-]{36}$/.test(fromBookmarklet) && window.opener) {
      nonce.current = fromBookmarklet;
      peer.current = window.opener;
      expiresAt.current = Date.now() + 180_000;
      waitingSince.current = Date.now();
      history.replaceState(null, '', location.pathname);
    }
    let disposed = false;
    async function receive(event: MessageEvent) {
      if (!validSyncMessage(event, peer.current, nonce.current)) return;
      if (importing.current) return;
      const data = event.data;
      if (data.type === 'hello') {
        if (!connected.current) {
          connected.current = true;
          waitingSince.current = Date.now();
          expiresAt.current = Date.now() + 180_000;
        }
        setNeedsHelper(false);
        setActive(true);
        setMessage('已连接官网，准备读取成绩…');
        send('ready');
      }
      if (data.type === 'progress') {
        connected.current = true;
        setNeedsHelper(false);
        setMessage('mai-tools 正在自动读取所有难度的成绩…');
      }
      if (data.type === 'error') {
        setMessage(data.message ?? '同步失败，请重新登录后重试。');
        setActive(false);
        peer.current = null;
      }
      if (data.type !== 'scores' || importing.current) return;
      importing.current = true;
      setSaving(true);
      send('received');
      setMessage('读取完成，正在保存成绩并计算推荐等级…');
      try {
        const response = await fetch('http://127.0.0.1:8000/v1/imports/mai-tools', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          signal: AbortSignal.timeout(30_000),
          body: JSON.stringify({ sourceOrigin: OFFICIAL_ORIGIN, scoreText: data.scoreText }),
        });
        const result = (await response.json()) as { id: string; issues: unknown[]; totalCount: number; detail?: string };
        if (!response.ok) throw new Error(result.detail ?? '成绩导入失败');
        if (result.issues.length === 0 && result.totalCount > 0) {
          const confirmed = await fetch(`http://127.0.0.1:8000/v1/imports/${result.id}/confirm`, { method: 'POST', signal: AbortSignal.timeout(30_000) });
          if (!confirmed.ok) throw new Error('成绩已保存，但确认失败。请重新同步或检查本地 API。');
        }
        send('saved');
        if (!disposed) window.location.assign(`/scores/${result.id}`);
      } catch (error: unknown) {
        send('error');
        if (!disposed) {
          setMessage(error instanceof Error ? error.message : '无法连接本地服务');
          setActive(false);
          setSaving(false);
        }
      }
    }
    window.addEventListener('message', receive);
    const timer = setInterval(() => {
      if (!peer.current || importing.current || checkingApi.current) return;
      const status = syncWaitStatus(connected.current, Date.now() - waitingSince.current, peer.current.closed);
      if (status === 'helper_missing' && !helperPrompted.current) {
        helperPrompted.current = true;
        setNeedsHelper(true);
        setMessage('未检测到 MaiUp 同步助手，尚未开始读取成绩。请在官网首页点击下方提供的「MaiUp 自动同步」书签，或启用已安装的 MaiUp 用户脚本。');
      }
      if (status === 'connection_closed' || Date.now() >= expiresAt.current) {
        send('cancel');
        peer.current = null;
        setActive(false);
        setMessage(status === 'connection_closed'
          ? '官网标签页已关闭，或浏览器断开了标签页连接。请在同一个浏览器中用 MaiUp 自动同步书签重试。'
          : connected.current
            ? '已连接助手，但 mai-tools 未在三分钟内完成读取。请检查官网标签页中的读取进度或错误。'
            : '未检测到 MaiUp 同步助手。请先保存并在官网运行下方的新书签；仅打开官网或运行原版 mai-tools 不会开始同步。');
      } else send('ready');
    }, 1000);
    return () => {
      disposed = true;
      clearInterval(timer);
      window.removeEventListener('message', receive);
    };
  }, []);

  async function start() {
    nonce.current = crypto.randomUUID();
    importing.current = false;
    connected.current = false;
    helperPrompted.current = false;
    checkingApi.current = true;
    setChecking(true);
    setNeedsHelper(false);
    setSaving(false);
    let opened: Window | null = null;
    try {
      const url = officialSyncUrl(location.origin, nonce.current);
      // Open during the click, before awaiting the local API, to preserve popup permission.
      opened = window.open('about:blank', '_blank');
      if (!opened) throw new Error('请允许打开官网标签页后重试。');
      peer.current = opened;
      setActive(true);
      setMessage('正在检查本地成绩服务…');
      await checkLocalCatalog();
      if (opened.closed) throw new Error('官网标签页已关闭，请重试。');
      waitingSince.current = Date.now();
      expiresAt.current = Date.now() + 180_000;
      opened.location.replace(url);
      setMessage('官网已打开。请在官网首页点击「MaiUp 自动同步」书签；已安装并启用 MaiUp 用户脚本时会自动开始。');
    } catch (error: unknown) {
      if (opened && !opened.closed) opened.close();
      peer.current = null;
      setActive(false);
      setMessage(error instanceof Error ? error.message : '无法打开官网');
    } finally {
      checkingApi.current = false;
      setChecking(false);
    }
  }

  async function helper(kind: 'userscript' | 'bookmarklet') {
    try {
      const response = await fetch('/maiup-sync.js');
      if (!response.ok) throw new Error('同步助手读取失败');
      const source = await response.text();
      if (kind === 'bookmarklet') {
        const code = 'javascript:' + encodeURIComponent(source);
        setBookmarklet(code);
        try { await navigator.clipboard.writeText(code); } catch { /* Selectable code is the fallback. */ }
        setMessage('将下面的代码保存为书签网址，在已登录的官网首页点击即可自动同步。');
      } else {
        const header = '// ==UserScript==\n// @name MaiUp official score sync\n// @namespace https://github.com/Zephyruz/MaiUp\n// @version 1.0.0\n// @description Automatically transfer mai-tools scores to local MaiUp when requested\n// @match https://maimaidx-eng.com/maimai-mobile/home/*\n// @run-at document-idle\n// @grant none\n// ==/UserScript==\n';
        const file = new Blob([header, "if (new URLSearchParams(location.hash.slice(1)).get('maiupAuto') === '1') {\n", source, '\n}'], { type: 'text/javascript' });
        const url = URL.createObjectURL(file);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'maiup-sync.user.js';
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 10_000);
        setMessage('在你的用户脚本管理器中导入下载的 maiup-sync.user.js，之后直接点击同步。');
      }
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : '助手下载失败');
    }
  }

  return <main className="min-h-screen bg-background p-6 text-foreground sm:p-10">
    <div className="mx-auto max-w-3xl space-y-6">
      <Link href="/" className="text-cyan-200 underline">返回 MaiUp</Link>
      <h1 className="font-display text-3xl font-bold">自动同步官网成绩</h1>
      <p className="leading-7 text-muted-foreground">请在你平时登录官网的浏览器中打开此页面。先保存下面的 MaiUp 书签，再在官网点击它；成绩读取、传回和推荐等级计算都会自动完成。</p>
      <section id="bookmarklet-setup" className="space-y-3 rounded-xl border border-cyan-300/30 p-5">
        <h2 className="text-lg font-semibold">首次设置：保存 MaiUp 自动同步书签</h2>
        <p className="text-sm leading-6">这是新的同步书签，不是原版 mai-tools 书签。请把下方链接拖到浏览器书签栏；也可以复制代码，新建书签并将代码填入「网址」。</p>
        {bookmarklet && <a href="#bookmarklet-setup" draggable
          ref={(element) => { if (element) element.href = bookmarklet; }}
          onClick={(event) => { event.preventDefault(); setMessage('请将链接拖到书签栏，然后在已登录的官网首页点击该书签。不要在 MaiUp 页面运行。'); }}
          className="inline-block rounded-xl bg-cyan-300 px-4 py-3 font-semibold text-slate-950">MaiUp 自动同步</a>}
        <p className="text-sm leading-6 text-muted-foreground">打开官网后应看到页面底部的 MaiUp 同步横幅。没有横幅表示助手未运行，等待不会开始读取。</p>
      </section>
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => helper('bookmarklet')}>复制自动同步书签</Button>
        <Button variant="outline" onClick={() => helper('userscript')}>下载用户脚本（可选，安装后自动运行）</Button>
      </div>
      <p className="text-sm leading-6 text-muted-foreground">助手需要浏览器用户脚本管理器。也可以使用书签：无需安装助手，在官网首页点击书签即可完成读取和导入。保持官网与 MaiUp 标签页打开。</p>
      {bookmarklet && <details>
        <summary className="cursor-pointer text-sm text-cyan-200">查看完整书签代码</summary>
        <label htmlFor="sync-bookmarklet" className="block text-sm">书签网址（完整复制）</label>
        <textarea id="sync-bookmarklet" readOnly value={bookmarklet} rows={3} onFocus={(event) => event.target.select()} className="mt-2 w-full rounded-xl border border-white/15 bg-background p-3 font-mono text-xs" />
      </details>}
      {needsHelper && <p className="rounded-xl border border-amber-300/40 p-4 text-amber-200">官网没有 MaiUp 横幅：请先完成上方书签设置，再去官网点击它。若已登录但没有反应，请确认使用了新的 MaiUp 书签。</p>}
      <Button onClick={start} disabled={active} className="bg-cyan-300 text-slate-950 hover:bg-cyan-200">{checking ? '检查本地服务…' : active ? '等待官网同步…' : '打开官网，然后运行 MaiUp 同步书签'}</Button>
      {active && <Button variant="outline" disabled={saving || checking} onClick={() => {
        send('cancel'); peer.current = null; setActive(false); setMessage('同步传输已取消。');
      }}>取消</Button>}
      <output aria-live="polite" className="block rounded-xl border border-cyan-300/20 p-4">{message}</output>
      <p className="text-sm leading-6 text-muted-foreground">匹配成功的成绩会自动保存并确认；遇到缺失或歧义谱面时会停在检查页。不会收集密码或 Cookie，也不会在后台定时读取账号。</p>
    </div>
  </main>;
}
