'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';

const BOOKMARKLET = 'javascript:(function(d){if(["https://maimaidx.jp","https://maimaidx-eng.com"].indexOf(d.location.origin)>=0){var s=d.createElement("script");s.src="https://myjian.github.io/mai-tools/scripts/all-in-one.js?t="+Math.floor(Date.now()/60000);d.body.append(s);}})(document)';

export default function MaiToolsImport() {
  const [text, setText] = useState('');
  const [international, setInternational] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function importScores(event: { preventDefault(): void }) {
    event.preventDefault();
    if (!international || !text.trim() || busy) return;
    setBusy(true);
    setMessage('正在匹配国际服曲库并计算 B50…');
    try {
      if (new TextEncoder().encode(text).length > 2_000_000) {
        throw new Error('成绩表不能超过 2 MB。');
      }
      const response = await fetch('http://127.0.0.1:8000/v1/imports/mai-tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourceOrigin: 'https://maimaidx-eng.com', scoreText: text }),
      });
      const result = (await response.json()) as { id?: string; detail?: unknown };
      if (!response.ok || !result.id) {
        throw new Error(typeof result.detail === 'string' ? result.detail : '成绩导入失败，请检查表格。');
      }
      window.location.assign(`/scores/${result.id}`);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : '无法连接本地服务');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={importScores} className="space-y-5 rounded-[2rem] border border-fuchsia-300/15 bg-card/70 p-6 sm:p-8">
      <div>
        <h2 className="font-display text-2xl font-bold">从官网导入成绩</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          使用 mai-tools 在已登录的官网读取成绩，再将成绩表粘贴到本机。MaiUp 不接收 SEGA ID、密码或 Cookie。
        </p>
      </div>
      <ol className="list-decimal space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
        <li>登录自己的 <a className="text-cyan-200 underline" href="https://maimaidx-eng.com/maimai-mobile/" target="_blank" rel="noreferrer">maimai DX NET 国际服</a>。</li>
        <li>按 <a className="text-cyan-200 underline" href="https://myjian.github.io/mai-tools/#howto" target="_blank" rel="noreferrer">mai-tools 安装说明</a>运行书签工具，打开成绩下载功能。</li>
        <li>保留 Song（歌曲）、Chart（谱面）、Difficulty（难度）、Achv（达成率）、FC/AP 列。需要 DX 分数时，将 DX Score 加入包含字段。</li>
        <li>点击 Load all scores（下载所有成绩），等待完成后点击 Copy（复制成绩），将包含表头的完整内容粘贴到下方。</li>
      </ol>
      <Button type="button" variant="outline" onClick={async () => {
        try {
          await navigator.clipboard.writeText(BOOKMARKLET);
          setMessage('已复制 mai-tools 书签代码，请按安装说明保存为书签并在官网运行。');
        } catch {
          setMessage('无法访问剪贴板，请使用上方 mai-tools 安装说明。');
        }
      }}>复制 mai-tools 书签代码</Button>
      <div>
        <label htmlFor="score-export" className="mb-2 block text-sm font-semibold">mai-tools 成绩表</label>
        <textarea id="score-export" value={text} onChange={(event) => setText(event.target.value)}
          required maxLength={2_000_000} rows={10} spellCheck={false}
          placeholder={'Song\tChart\tDifficulty\tAchv\tFC/AP'}
          className="w-full rounded-xl border border-white/15 bg-background p-3 font-mono text-xs" />
      </div>
      <label className="flex items-start gap-3 text-sm leading-6">
        <input type="checkbox" checked={international} onChange={(event) => setInternational(event.target.checked)} required className="mt-1.5" />
        此成绩表来自我自己的 maimaidx-eng.com 国际服账号，并已完成所有难度的读取。
      </label>
      <p className="text-xs leading-5 text-muted-foreground">
        当前仅支持国际服。导出表无法自动验证服务器或完整性，也不包含逐次游玩历史。所有导入行都会保留；B50 使用本地社区曲库的定数和版本重新计算。
      </p>
      <Button type="submit" disabled={busy || !international || !text.trim()} className="bg-cyan-300 text-slate-950 hover:bg-cyan-200">
        {busy ? '导入中…' : '导入并检查成绩'}
      </Button>
      <output aria-live="polite" className="text-sm text-cyan-100">{message}</output>
    </form>
  );
}
