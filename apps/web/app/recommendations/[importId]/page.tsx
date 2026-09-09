'use client';

import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  CircleGauge,
  Database,
  Loader2,
  Music2,
  Sparkles,
  ShieldAlert,
  Target,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const API_ORIGIN = 'http://127.0.0.1:8000';

type Evidence = {
  sampleCount: number;
  hitCount: number;
  hitRate: string;
  strength: 'strong' | 'limited' | 'insufficient';
  isSuccessProbability: false;
};

type StrengthConfidence = 'strong' | 'limited' | 'exploratory';

type FitReason = {
  nameEn: string;
  nameZhHans: string;
  sampleCount: number;
  confidence: StrengthConfidence;
};

type TargetEvidence = {
  sampleCount: number;
  hitCount: number;
  hitRate: string;
  basis: 'player_exact' | 'player_nearby' | 'community_water_exception';
  comfortTier: 0 | 1;
  isSuccessProbability: false;
};

type PersonalStrength = FitReason & {
  tagId: number;
  meanResidual: string;
  score: string;
};

type Recommendation = {
  kind: 'in_list' | 'outside_b50';
  strategy?: 'steady' | 'sprint';
  slot?: number;
  chartId: string;
  title: string;
  coverUrl?: string | null;
  artist?: string;
  chartType: string;
  difficulty: string;
  bucket: 'b35' | 'b15';
  version?: string;
  constant: string;
  currentAchievement?: string;
  currentRating?: number;
  targetAchievement: string;
  targetRating: number;
  replacementThreshold?: number;
  conditionalGain: number;
  achievementGap?: string;
  personalFitScore?: string;
  fitReasons?: FitReason[];
  targetEvidence?: TargetEvidence;
  communityDifficulty?: 'water' | 'mine' | 'neutral';
  recommendationBasis?: 'personalized' | 'comfort_fallback';
  evidence: Evidence;
  constantDerivation?: string;
  fact: string;
};

type RecommendationResult = {
  importId: string;
  status: 'experimental';
  algorithmVersion: string;
  coverage: 'best50_only';
  totalRating: number;
  thresholds: { b35: number; b15: number };
  profile: Record<
    'b35' | 'b15',
    {
      entryCount: number;
      constantMin: string;
      constantMax: string;
      medianAchievement: string;
      atOrAbove100_5: number;
    }
  >;
  personalProfile: {
    method: string;
    strengths: PersonalStrength[];
    isCausal: false;
  };
  inList: Recommendation[];
  outside: Recommendation[];
  provenance: {
    catalogSnapshotId: string;
    catalogSource: string;
    constantsAreOfficial: false;
  };
  caveats: string[];
};

const strengthText = {
  strong: 'B50 证据较足',
  limited: 'B50 证据有限',
  insufficient: 'B50 证据不足',
};

const strengthStyle = {
  strong: 'border-lime-300/25 bg-lime-300/8 text-lime-100',
  limited: 'border-amber-300/25 bg-amber-300/8 text-amber-100',
  insufficient: 'border-rose-300/25 bg-rose-300/8 text-rose-100',
};

const confidenceText: Record<StrengthConfidence, string> = {
  strong: '证据较足',
  limited: '证据有限',
  exploratory: '探索性',
};

function tagLabel(item: { nameEn: string; nameZhHans: string }) {
  return item.nameZhHans || item.nameEn;
}

function RecommendationCard({ item }: { item: Recommendation }) {
  const bucketPosition = item.slot
    ? item.bucket === 'b15' ? item.slot - 35 : item.slot
    : null;

  return (
    <article className="rounded-2xl border border-white/8 bg-white/3 p-4">
      <div className="flex items-start gap-4">
        <div className="relative size-24 shrink-0 overflow-hidden rounded-xl border border-white/10 bg-slate-950/70 sm:size-28">
          <div className="absolute inset-0 grid place-items-center">
            <Music2 className="size-8 text-white/20" />
          </div>
          {item.coverUrl && (
            <Image
              src={item.coverUrl}
              alt={`${item.title} 曲绘`}
              fill
              sizes="(max-width: 640px) 96px, 112px"
              unoptimized
              className="relative size-full object-cover"
              onError={(event) => { event.currentTarget.style.display = 'none'; }}
            />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {bucketPosition ? (
              <Badge
                variant="outline"
                className={item.bucket === 'b35' ? 'border-cyan-300/25 text-cyan-200' : 'border-lime-300/25 text-lime-200'}
              >
                {item.bucket.toUpperCase()} #{bucketPosition}
              </Badge>
            ) : (
              <Badge
                variant="outline"
                className={item.bucket === 'b35' ? 'border-cyan-300/25 text-cyan-200' : 'border-lime-300/25 text-lime-200'}
              >
                {item.bucket.toUpperCase()}
              </Badge>
            )}
            {item.strategy && (
              <Badge variant="outline" className="border-white/10 text-muted-foreground">
                {item.strategy === 'steady' ? '稳健目标' : '冲刺目标'}
              </Badge>
            )}
            {item.communityDifficulty === 'water' && (
              <Badge className="bg-lime-300 text-slate-950">DXRating 社区水歌</Badge>
            )}
          </div>
          <h3 className="mt-3 line-clamp-2 break-all font-display text-lg font-bold">{item.title}</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            {item.chartType} · {item.difficulty} · 定数 {item.constant}
            {item.version ? ` · ${item.version}` : ''}
          </p>
          <div className="mt-3 flex items-center gap-3">
            <div className="rounded-xl bg-cyan-300/10 px-3 py-2 text-center">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground">条件增益</p>
              <p className="mt-0.5 text-xl font-black text-cyan-200">+{item.conditionalGain}</p>
            </div>
            {item.currentAchievement && (
              <div>
                <p className="text-[10px] text-muted-foreground">当前 Achievement</p>
                <p className="font-mono text-sm font-bold text-white">{item.currentAchievement}%</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-xl bg-slate-950/45 p-3">
          <p className="text-xs text-muted-foreground">目标 Achievement</p>
          <p className="mt-1 font-mono font-bold text-white">{item.targetAchievement}%</p>
        </div>
        <div className="rounded-xl bg-slate-950/45 p-3">
          <p className="text-xs text-muted-foreground">目标单谱 Rating</p>
          <p className="mt-1 font-bold text-white">{item.targetRating}</p>
        </div>
      </div>

      <p className="mt-3 text-xs leading-5 text-slate-200">{item.fact}</p>
      {item.kind === 'outside_b50' && item.targetEvidence && (
        <div className="mt-3 rounded-xl border border-cyan-300/20 bg-cyan-300/7 p-3 text-xs text-cyan-50">
          {item.targetEvidence.basis === 'community_water_exception'
            ? '你的 B50 尚未证明这个定数目标；仅因 DXRating 社区标记为“水”而保留，并已降低优先级。'
            : `你的 B50 在${item.targetEvidence.basis === 'player_exact' ? '同定数' : '邻近定数'}有 ${item.targetEvidence.hitCount}/${item.targetEvidence.sampleCount} 项达到该目标。`}
        </div>
      )}
      {item.kind === 'outside_b50' && item.fitReasons?.length ? (
        <div className="mt-3 flex items-start gap-3 rounded-xl border border-lime-300/25 bg-lime-300/8 p-3 text-lime-100">
          <Sparkles className="mt-0.5 size-5 shrink-0" />
          <div>
            <p className="text-sm font-black">含有你相对擅长的元素</p>
            <p className="mt-1 text-sm font-bold">
              {item.fitReasons.map(tagLabel).join(' · ')}
            </p>
            <p className="mt-1 text-xs opacity-75">
              {item.fitReasons.map((reason) => `${tagLabel(reason)} ${reason.sampleCount} 项`).join('；')}。标签只描述其中的元素，不代表整张谱的唯一类型。
            </p>
          </div>
        </div>
      ) : item.kind === 'outside_b50' ? (
        <div className="mt-3 flex items-start gap-3 rounded-xl border border-white/10 bg-white/4 p-3 text-slate-200">
          <Target className="mt-0.5 size-5 shrink-0 text-cyan-200" />
          <div>
            <p className="text-sm font-black">舒适段补充候选</p>
            <p className="mt-1 text-xs text-muted-foreground">未匹配当前识别出的优势元素，但你的 B50 已证明这个定数目标可达，且没有“诈称谱”标签。</p>
          </div>
        </div>
      ) : (
        <div className={`mt-3 flex items-start gap-3 rounded-xl border p-3 ${strengthStyle[item.evidence.strength]}`}>
          <CircleGauge className="mt-0.5 size-5 shrink-0" />
          <div>
            <p className="text-sm font-black">{strengthText[item.evidence.strength]}</p>
            <p className="mt-1 text-xs opacity-75">相近定数记录 {item.evidence.sampleCount} 项，其中 {item.evidence.hitCount} 项达到目标；这不是成功率。</p>
          </div>
        </div>
      )}
    </article>
  );
}

export default function RecommendationsPage() {
  const params = useParams<{ importId: string }>();
  const [result, setResult] = useState<RecommendationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_ORIGIN}/v1/imports/${params.importId}/recommendations?limit_per_bucket=10`)
      .then(async (response) => {
        const payload = (await response.json()) as RecommendationResult & { detail?: string };
        if (!response.ok) throw new Error(payload.detail ?? `推荐生成失败 (${response.status})`);
        return payload;
      })
      .then(setResult)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : '推荐生成失败'));
  }, [params.importId]);

  const outsideGroups = useMemo(() => {
    if (!result) return { b35: [], b15: [] };
    return {
      b35: result.outside.filter((item) => item.bucket === 'b35'),
      b15: result.outside.filter((item) => item.bucket === 'b15'),
    };
  }, [result]);

  if (!result) {
    return (
      <main className="grid min-h-screen place-items-center bg-background px-4 text-foreground">
        <div className="text-center">
          {error ? <ShieldAlert className="mx-auto size-8 text-amber-200" /> : <Loader2 className="mx-auto size-8 animate-spin text-cyan-300" />}
          <p className="mt-3 text-sm text-muted-foreground">{error ?? '正在根据已确认 B50 计算候选…'}</p>
          {error && <Link href={`/review/${params.importId}`} className="mt-4 inline-block text-sm text-cyan-200">返回 B50</Link>}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-background px-4 py-6 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="border-b border-white/8 pb-6">
          <Link href={`/review/${params.importId}`} className="inline-flex items-center gap-2 text-sm text-cyan-200 hover:text-cyan-100">
            <ArrowLeft className="size-4" /> 返回已确认 B50
          </Link>
          <div className="mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <div className="flex items-center gap-2">
                <p className="eyebrow">EXPERIMENTAL V0.6</p>
                <Badge className="bg-amber-300 text-slate-950">实验推荐</Badge>
              </div>
              <h1 className="mt-2 font-display text-3xl font-black tracking-tight sm:text-4xl">你的首版上分候选</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                榜外先确认你在同定数或邻近定数证明过目标成绩，再比较实际加分和擅长元素。
              </p>
            </div>
            <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/6 px-5 py-4">
              <p className="text-xs text-muted-foreground">当前总 Rating</p>
              <p className="mt-1 text-3xl font-black text-cyan-200">{result.totalRating}</p>
            </div>
          </div>
        </header>

        <section className="mt-6 grid gap-4 sm:grid-cols-2">
          {(['b35', 'b15'] as const).map((bucket) => (
            <div key={bucket} className="rounded-2xl border border-white/8 bg-card/55 p-5">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-bold">{bucket.toUpperCase()} 已证明范围</h2>
                <span className="font-bold text-cyan-200">门槛 {result.thresholds[bucket]}</span>
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                定数 {result.profile[bucket].constantMin}–{result.profile[bucket].constantMax} · Achievement 中位数 {result.profile[bucket].medianAchievement}% · {result.profile[bucket].atOrAbove100_5} 项达到 100.5%
              </p>
            </div>
          ))}
        </section>

        <section className="mt-6 rounded-2xl border border-lime-300/15 bg-lime-300/5 p-5">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-lime-200" />
            <h2 className="font-display text-xl font-bold">从 B50 推断的相对擅长元素</h2>
          </div>
          {result.personalProfile.strengths.length ? (
            <div className="mt-4 flex flex-wrap gap-3">
              {result.personalProfile.strengths.map((strength) => (
                <div key={strength.tagId} className="min-w-44 rounded-xl border border-white/8 bg-slate-950/35 px-4 py-3">
                  <p className="font-bold text-lime-100">{tagLabel(strength)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {strength.sampleCount} 项 · 相近定数平均高 {strength.meanResidual}% · {confidenceText[strength.confidence]}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">这张 B50 还没有形成达到最低样本量的优势标签。</p>
          )}
          <p className="mt-3 text-xs leading-5 text-amber-100/75">
            只比较同分区、定数相差不超过 0.2 的 B50 成绩，并对小样本降权；一张谱通常包含多种元素，单个标签不等于整张谱的类型。
          </p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            当前 B50 的成绩已经一起用于判断舒适定数、目标达成依据和擅长元素，因此不再逐首重复展开推荐卡。
          </p>
        </section>

        <section className="mt-10">
          <div className="flex items-center gap-3">
            <Target className="size-5 text-lime-200" />
            <div>
              <p className="eyebrow">CONDITIONAL CANDIDATES</p>
              <h2 className="font-display text-2xl font-bold">值得尝试的榜外谱面</h2>
              <p className="mt-1 text-sm text-amber-100/80">先展示优势元素匹配，再用舒适段内、目标可达且非诈称的谱面补足数量；社区“水”标签会标绿。</p>
            </div>
          </div>
          {(['b35', 'b15'] as const).map((bucket) => (
            <div key={bucket} className="mt-6">
              <h3 className="text-sm font-bold text-muted-foreground">{bucket.toUpperCase()} 候选 · {outsideGroups[bucket].length} 首</h3>
              <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {outsideGroups[bucket].map((item) => <RecommendationCard key={item.chartId} item={item} />)}
              </div>
            </div>
          ))}
        </section>

        <section className="mt-10 rounded-3xl border border-amber-300/15 bg-amber-300/5 p-5 sm:p-6">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-5 text-amber-200" />
            <h2 className="font-display text-lg font-bold">使用限制</h2>
          </div>
          <ul className="mt-4 space-y-2 text-sm leading-6 text-muted-foreground">
            {result.caveats.map((item) => <li key={item}>• {item}</li>)}
          </ul>
          <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-white/8 pt-4 text-xs text-muted-foreground">
            <Database className="size-4" />
            曲库：DXRating 公开社区目录 · 定数不是 SEGA 官方数据 · 算法 {result.algorithmVersion}
          </div>
        </section>
      </div>
    </main>
  );
}
