export interface RankDef {
  minAchv: number;
  factor: number;
  title: string;
  maxAchv?: number;
  maxFactor?: number;
}
export interface RecommendedLevel {
  lv: number;
  minAchv: number;
  rating: number;
}
export function getRankDefinitions(): readonly RankDef[];
export function calcRecommendedLevels(rating: number, ranks: RankDef[]): Record<string, RecommendedLevel[]>;
