'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import MaiToolsRecommendedLevels from '@/app/mai-tools-recommended-levels';

type Score = {
  row: number;
  title: string;
  chartType: string;
  difficulty: string;
  achievement: string;
  fullCombo: string | null;
  sync?: string;
  dxScore?: string;
  dxRatio?: string;
  dxStar?: string;
  calculatedRating?: number;
  issueCode: string | null;
};
type ScoreExport = {
  id: string;
  status: string;
  totalRating: number | null;
  totalCount: number;
  scores: Score[];
  issues: { row: number; title: string; code: string }[];
  entries: { chartId: string; title: string; bucket: string; calculatedRating: number }[];
};

const API_ORIGIN = 'http://127.0.0.1:8000';
const PAGE_SIZE = 50;
const issueLabels: Record<string, string> = {
  chart_not_found: '曲库未找到',
  ambiguous_chart: '存在多个匹配',
  chart_not_rating_eligible: '不属于当前计分池',
};

export default function ScoreReviewPage() {
  const { importId } = useParams<{ importId: string }>();
  const [data, setData] = useState<ScoreExport | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_ORIGIN}/v1/imports/${importId}/scores`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error('无法读取成绩导入');
        return response.json() as Promise<ScoreExport>;
      }).then(setData).catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setMessage(error instanceof Error ? error.message : '成绩读取失败');
      });
    return () => controller.abort();
  }, [importId]);

  async function confirm() {
    setBusy(true);
    try {
      const response = await fetch(`${API_ORIGIN}/v1/imports/${importId}/confirm`, { method: 'POST' });
      const result = (await response.json()) as { status: string; detail?: string };
      if (!response.ok) throw new Error(result.detail ?? '确认失败');
      setData((previous) => previous ? { ...previous, status: result.status } : previous);
      setMessage('成绩已确认并锁定。');
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : '确认失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-background p-5 text-foreground sm:p-10">
      <div className="mx-auto max-w-6xl space-y-6">
        <Link href="/" className="text-cyan-200 underline">返回导入</Link>
        <h1 className="font-display text-3xl font-bold">官网成绩检查</h1>
        <output aria-live="polite" className="text-cyan-100">{message}</output>
        {!data ? <p>正在读取成绩…</p> : <>
          <p>已保留 {data.scores.length} 条成绩 · 选入 B50 {data.totalCount} 条 · {data.issues.length ? '暂定' : '计算'} Rating {data.totalRating ?? 0}</p>
          <p className="text-sm leading-6 text-muted-foreground">
            来源：用户声明的国际服 mai-tools 导出。定数来自 MaiUp 社区曲库，并非官方定数。
            此表是当前成绩快照，不是逐次游玩历史；缺少的曲目不能视为未游玩。当前推荐仍只使用选出的 B50。
          </p>
          {data.issues.length > 0 && <div className="rounded-xl border border-amber-300/40 p-4">
            <p>以下行尚未匹配，当前 B50 不完整，暂不能确认。请检查原表曲名和曲库版本，然后重新导入；不要删除有问题的成绩来绕过检查。</p>
            <ul className="mt-2 max-h-48 list-disc overflow-auto pl-5 text-sm">
              {data.issues.map((issue) => <li key={issue.row}>第 {issue.row} 行 · {issue.title} · {issueLabels[issue.code] ?? issue.code}</li>)}
            </ul>
          </div>}
          <MaiToolsRecommendedLevels entries={data.entries} provisional={data.issues.length > 0} />
          <details className="rounded-xl border border-white/15 p-4">
            <summary className="cursor-pointer font-semibold">查看计算出的 B35 / B15</summary>
            <ul className="mt-3 max-h-80 space-y-1 overflow-auto text-sm">
              {data.entries.map((entry) => <li key={entry.chartId}>{entry.bucket.toUpperCase()} · {entry.title} · {entry.calculatedRating}</li>)}
            </ul>
          </details>
          <div className="overflow-x-auto rounded-xl border border-white/15">
            <table className="w-full whitespace-nowrap text-left text-sm">
              <caption className="p-3 text-left">全部导入成绩（第 {page + 1} / {Math.max(1, Math.ceil(data.scores.length / PAGE_SIZE))} 页）</caption>
              <thead><tr>{['歌曲', '谱面 / 难度', '达成率', 'FC/AP', 'Sync', 'DX 分数 / % / 星', 'Rating'].map((title) => <th scope="col" key={title} className="p-3">{title}</th>)}</tr></thead>
              <tbody>{data.scores.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((score) => <tr key={score.row} className="border-t border-white/10">
                <td className="p-3">{score.title}</td><td className="p-3">{score.chartType.toUpperCase()} / {score.difficulty}</td>
                <td className="p-3">{score.achievement}%</td><td className="p-3">{score.fullCombo ?? '-'}</td>
                <td className="p-3">{score.sync ?? '-'}</td><td className="p-3">{score.dxScore ?? '-'} / {score.dxRatio ?? '-'} / {score.dxStar ?? '-'}</td>
                <td className="p-3">{score.issueCode ? (issueLabels[score.issueCode] ?? score.issueCode) : score.calculatedRating}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>上一页</Button>
            <Button variant="outline" disabled={(page + 1) * PAGE_SIZE >= data.scores.length} onClick={() => setPage(page + 1)}>下一页</Button>
          </div>
          {data.status === 'confirmed' ? <p>成绩已确认并锁定。</p> : <Button onClick={confirm} disabled={busy || data.issues.length > 0 || data.totalCount === 0}>确认这份成绩</Button>}
          {data.status === 'confirmed' && data.totalCount === 50 && <p><Link className="text-cyan-200 underline" href={`/recommendations/${data.id}`}>查看 B50 推荐</Link></p>}
          {data.totalCount < 50 && <p className="text-sm text-muted-foreground">可以保存不足 50 条的成绩；当前实验推荐需要完整的 B35 + B15。</p>}
        </>}
      </div>
    </main>
  );
}
