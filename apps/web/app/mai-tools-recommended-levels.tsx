'use client';

import { calcRecommendedLevels, getRankDefinitions } from '@/vendor/mai-tools/rank-functions.js';

type Entry = { bucket: string; calculatedRating: number | null };
type Props = { provisional?: boolean } & (
  { entries: Entry[]; thresholds?: never } |
  { entries?: never; thresholds: { b35: number; b15: number } }
);

export default function MaiToolsRecommendedLevels({ entries, thresholds, provisional = false }: Props) {
  const ranks = getRankDefinitions().filter((rank) => rank.minAchv >= 99);
  const buckets = [{ key: 'b15', label: '新谱面 B15', size: 15 }, { key: 'b35', label: '旧谱面 B35', size: 35 }] as const;
  return <section className="space-y-4 rounded-2xl border border-fuchsia-300/25 bg-card/70 p-5">
    <h2 className="font-display text-xl font-bold">mai-tools 推荐等级</h2>
    <p className="text-sm leading-6 text-muted-foreground">
      使用 mai-tools 原版推荐等级算法：列出 SS、SS+、SSS、SSS+ 下，超过当前计分池最低 Rating 所需的谱面定数与达成率。
      定数和 B35/B15 分区沿用这份 MaiUp 导入。它是上分目标表，不是个性化难度预测。
    </p>
    {provisional && <p className="text-amber-200">有成绩尚未匹配，下表仅供预览，最低项可能变化。</p>}
    {buckets.map((bucket) => {
      const ratings = (entries ?? []).filter((entry) => entry.bucket === bucket.key && entry.calculatedRating !== null)
        .map((entry) => entry.calculatedRating as number);
      if (!thresholds && ratings.length < bucket.size) return <p key={bucket.key} className="text-sm text-muted-foreground">{bucket.label}：目前 {ratings.length}/{bucket.size} 项，填满后显示替换目标。</p>;
      const threshold = thresholds ? thresholds[bucket.key] : Math.min(...ratings);
      if (threshold <= 0) return <p key={bucket.key} className="text-sm">{bucket.label}：最低 Rating 为 0，mai-tools 暂不生成推荐等级。</p>;
      const levels = calcRecommendedLevels(threshold + 1, ranks);
      const rows = ranks.flatMap((rank) => levels[rank.title].map((level) => ({ rank: rank.title, ...level })));
      return <div key={bucket.key} className="overflow-x-auto">
        <h3 className="mb-3 font-semibold">{bucket.label} · 当前最低 {threshold} · 目标 ≥ {threshold + 1}</h3>
        {rows.length === 0 ? <p className="text-sm">在 mai-tools 支持的最高定数 15.0 内没有更高目标。</p> :
          <table className="w-full whitespace-nowrap text-left text-sm">
            <thead><tr>{['定数', 'Rank', '最低达成率', 'Rating'].map((heading) => <th scope="col" key={heading} className="p-2">{heading}</th>)}</tr></thead>
            <tbody>{rows.map((row) => <tr key={`${row.rank}-${row.lv.toFixed(1)}`} className="border-t border-white/10">
              <td className="p-2">{row.lv.toFixed(1)}</td><td className="p-2">{row.rank}</td>
              <td className="p-2">{row.minAchv.toFixed(4)}%</td><td className="p-2">{row.rating}</td>
            </tr>)}</tbody>
          </table>}
      </div>;
    })}
    <p className="text-xs leading-5 text-muted-foreground">
      算法保留上游的浮点取整方式，目标不含 AP 加分，也不使用临近 Rank 上限的额外系数。
      <a className="ml-1 text-cyan-200 underline" href="https://github.com/myjian/mai-tools/blob/1d1ce89b76950816845e5f82707ab108ae35d0a0/src/common/rank-functions.ts" target="_blank" rel="noreferrer">mai-tools 源码与署名</a>
    </p>
  </section>;
}
