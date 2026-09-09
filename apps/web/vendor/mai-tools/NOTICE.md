# mai-tools recommended-level calculation

Source: https://github.com/myjian/mai-tools
Revision: `1d1ce89b76950816845e5f82707ab108ae35d0a0`
Upstream author: Ming-Yuan Jian (myjian) and contributors.

`rank-functions.js` and `number-helper.js` are derived from
`src/common/rank-functions.ts` and `src/common/number-helper.ts` at that revision.
The original repository's GNU GPL v3 license is included in `LICENSE`.

Changes: TypeScript types were removed for runtime use; the upstream
`level-helper.ts` constant `MAX_LEVEL = 15` is inlined; the number-helper import
has an explicit `.js` extension. The rank definitions and recommended-level
algorithm are unchanged. The adjacent declaration file is the MaiUp adapter.

The algorithm intentionally follows upstream floating-point rounding and its
choice to omit the near-rank maximum factors. It does not add the AP bonus to
targets. MaiUp's existing Decimal score calculator remains separate.
