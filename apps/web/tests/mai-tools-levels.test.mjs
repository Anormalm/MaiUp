import assert from 'node:assert/strict';
import { test } from 'node:test';
import { calcRecommendedLevels, getRankDefinitions } from '../vendor/mai-tools/rank-functions.js';

const ranks = getRankDefinitions().filter((rank) => rank.minAchv >= 99);

test('mai-tools targets for cutoff 314 require 14.0 SSS+ or 14.6 SSS', () => {
  const result = calcRecommendedLevels(315, ranks);
  assert.deepEqual(result['SSS+'], [{ lv: 14, minAchv: 100.5, rating: 315 }]);
  assert.equal(result.SSS[0].lv.toFixed(1), '14.6');
  assert.equal(result.SSS[0].minAchv, 100);
  assert.equal(result.SSS[0].rating, 315);
  assert.deepEqual(result['SS+'], []);
  assert.deepEqual(result.SS, []);
});

test('all offered targets beat the requested cutoffs and stay within upstream limits', () => {
  for (const cutoff of [100, 200, 270, 290, 300, 314, 330, 337]) {
    const byRank = calcRecommendedLevels(cutoff + 1, ranks);
    for (const rank of ranks) {
      for (const row of byRank[rank.title]) {
        assert.ok(row.lv <= 15);
        assert.ok(row.minAchv >= rank.minAchv && row.minAchv <= 100.5);
        assert.ok(row.rating > cutoff);
        assert.equal(row.rating, Math.floor(row.lv * rank.factor * row.minAchv));
      }
    }
  }
  assert.ok(Object.values(calcRecommendedLevels(338, ranks)).every((rows) => rows.length === 0));
});
