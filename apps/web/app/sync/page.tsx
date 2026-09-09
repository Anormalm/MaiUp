'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { OFFICIAL_ORIGIN, SYNC_PROTOCOL, officialSyncUrl, validSyncMessage } from '@/lib/official-sync';

export default function SyncPage() {
  const peer = useRef<Window | null>(null);
  const nonce = useRef('');
  const importing = useRef(false);
  const expiresAt = useRef(0);
  const [message, setMessage] = useState('安装一次同步助手后，点击同步即可自动读取官网成绩。');
  const [active, setActive] = useState(false);
  const [saving, setSaving] = useState(false);
  const [bookmarklet, setBookmarklet] = useState('');

  function send(type: string) {
    peer.current?.postMessage({ protocol: SYNC_PROTOCOL, nonce: nonce.current, type }, OFFICIAL_ORIGIN);
  }

  useEffect(() => {
    const fragment = new URLSearchParams(location.hash.slice(1));
    const fromBookmarklet = fragment.get('maiupNonce');
    if (fromBookmarklet && /^[a-f0-9-]{36}$/.test(fromBookmarklet) && window.opener) {
      nonce.current = fromBookmarklet;
      peer.current = window.opener;
      expiresAt.current = Date.now() + 180_000;
      history.replaceState(null, '', location.pathname);
    }
    let disposed = false;
    async function receive(event: MessageEvent) {
      if (!validSyncMessage(event, peer.current, nonce.current)) return;
      if (importing.current) return;
      const data = event.data;
      if (data.type === 'hello') {
        setActive(true);
        setMessage('已连接官网，准备读取成绩…');
        send('ready');
      }
      if (data.type === 'progress') setMessage('mai-tools 正在自动读取所有难度的成绩…');
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
      if (!peer.current || importing.current) return;
      if (peer.current.closed || Date.now() >= expiresAt.current) {
        send('cancel');
        peer.current = null;
        setActive(false);
        setMessage('连接超时或官网标签页已关闭。如果官网要求登录，请登录后返回此页重新同步。');
      } else send('ready');
    }, 1000);
    return () => {
      disposed = true;
      clearInterval(timer);
      window.removeEventListener('message', receive);
    };
  }, []);

  function start() {
    nonce.current = crypto.randomUUID();
    importing.current = false;
    setSaving(false);
    expiresAt.current = Date.now() + 180_000;
    try {
      peer.current = window.open(officialSyncUrl(location.origin, nonce.current), '_blank');
      if (!peer.current) throw new Error('请允许打开官网标签页后重试。');
      setActive(true);
      setMessage('官网已打开。已安装助手会自动同步；若需要登录，登录后返回这里重新点击同步。');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : '无法打开官网');
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
      <p className="leading-7 text-muted-foreground">在你平时登录 maimai DX NET 的同一个浏览器打开此页面。登录仍在官网完成；同步助手会自动调用 mai-tools、读取全部成绩，并带回 MaiUp 的推荐等级表。</p>
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => helper('userscript')}>下载一次性安装的同步助手</Button>
        <Button variant="outline" onClick={() => helper('bookmarklet')}>复制自动同步书签</Button>
      </div>
      <p className="text-sm leading-6 text-muted-foreground">助手需要浏览器用户脚本管理器。也可以使用书签：无需安装助手，在官网首页点击书签即可完成读取和导入。保持官网与 MaiUp 标签页打开。</p>
      {bookmarklet && <div>
        <label htmlFor="sync-bookmarklet" className="block text-sm">书签网址（完整复制）</label>
        <textarea id="sync-bookmarklet" readOnly value={bookmarklet} rows={3} onFocus={(event) => event.target.select()} className="mt-2 w-full rounded-xl border border-white/15 bg-background p-3 font-mono text-xs" />
      </div>}
      <Button onClick={start} disabled={active} className="bg-cyan-300 text-slate-950 hover:bg-cyan-200">{active ? '同步中…' : '同步官网成绩并生成推荐等级'}</Button>
      {active && <Button variant="outline" disabled={saving} onClick={() => {
        send('cancel'); peer.current = null; setActive(false); setMessage('同步传输已取消。');
      }}>取消</Button>}
      <output aria-live="polite" className="block rounded-xl border border-cyan-300/20 p-4">{message}</output>
      <p className="text-sm leading-6 text-muted-foreground">匹配成功的成绩会自动保存并确认；遇到缺失或歧义谱面时会停在检查页。不会收集密码或 Cookie，也不会在后台定时读取账号。</p>
    </div>
  </main>;
}
