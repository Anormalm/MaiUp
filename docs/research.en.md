# MaiUp Research Notes

Last reviewed: 2026-09-09.

## Product scope

MaiUp targets maimai DX International players who want explainable score-improvement suggestions. It supports a local B50 image import with OCR and mandatory review, and is designed to add structured imports of broader play records.

A B50 contains only a player's selected top scores. It can estimate a demonstrated comfort range, but it cannot distinguish unplayed charts from played charts that did not enter the B50. Recommendations based only on B50 data must expose that limitation.

## Data sources

DXRating is the primary catalog source. It supplies songs, charts, regional availability, versions, constants, note counts, aliases, and community tags. MaiUp stores the exact response as an immutable hash-addressed snapshot, validates it, and records provenance before publication.

DXRating values are community-maintained and must not be described as official SEGA International constants. The current catalog does not provide a separately authoritative International constant for every chart, so MaiUp marks fallback constants with reduced confidence and supports explicit regional overrides.

Technique and style tags are weak evidence. A chart may contain several elements, so one tag is never treated as its sole identity. Relevant community meanings include:

- `Overrated`: the displayed constant is considered generous, commonly interpreted as a water chart;
- `Underrated`: the displayed constant is considered too low, commonly interpreted as risky or deceptively difficult;
- technique/style tags such as Trill, Slide-heavy, Tap-heavy, Foundation, Stamina, and Deciphering.

These labels are opinions rather than objective measurements. MaiUp displays their source and does not convert them into unsupported success probabilities.

Secondary community catalogs may be used for discrepancy checks, but matching values are not automatically independent evidence when projects share upstream data. CN statistics may be used only after chart identity is verified and must remain labeled as cross-region priors.

## Rating and version rules

The chart Rating implementation uses exact decimal thresholds, floors the result, caps the Achievement multiplier at 100.5%, and adds one Rating for AP or AP+. Boundary behavior is covered by automated tests.

For the configured CiRCLE PLUS International snapshot, B15 contains CiRCLE PLUS and CiRCLE charts, while B35 contains eligible charts from earlier versions. Special and Utage charts are excluded. Version membership is derived from ordered catalog metadata rather than hard-coded names.

## B50 recognition

The local OCR pipeline recognizes song identity, chart type, difficulty, displayed constant, Achievement, rank, chart Rating, and green FC/FC+ markers. Blue Sync markers are intentionally ignored. Low-confidence fields remain reviewable, and all 50 entries must pass consistency checks before confirmation. Confirmed imports are immutable.

One saved JiETNG International fixture currently matches 50/50 entries, reproduces total Rating 15,150, and identifies 25 FC markers. This is a template-specific regression result, not a universal OCR accuracy claim.

## Recommendation baseline

The experimental `b50-personal-fit-v0.6` model:

1. calculates current B35/B15 replacement thresholds;
2. estimates demonstrated target attainment at the same or a nearby constant;
3. derives small-sample-shrunk element signals from B50 residuals;
4. excludes current B50 charts and ordinary risky-tag candidates;
5. ranks demonstrated personalized candidates before comfort-range fallbacks;
6. displays conditional Rating gain separately from uncertain evidence.

Recommendations prioritize charts outside the current B50. “Outside B50” never means “unplayed.” Community water-chart tags are positive signals, risky tags are excluded from ordinary recommendations, and repeated constants are capped to preserve variety.

## Complete score import

Complete records are the next major data improvement because they can identify unplayed charts, scores below the B50 threshold, broader strengths and weaknesses, and realistic targets by level and chart element.

The preferred prototype is a user-side bookmarklet that runs after the player logs into the official maimai DX NET site. It should export processed score data without reading or storing the SEGA password. Direct credential storage and server-side login are outside the first implementation.

Any automated interaction with an official service requires a separate terms, privacy, and operational review. A bookmarklet is safer than collecting credentials, but it is not a claim of official authorization.

## Validation gates

Before calibrated probabilities or automatic `+10 Rating` plans are enabled, MaiUp needs multiple real International players, broader score histories, cross-player holdouts, calibration metrics, community-tag ablations, explicit unseen-chart handling, and reproducible outputs tied to catalog and algorithm versions.

Until then, the UI must distinguish formula-derived facts from model evidence and must never promise that a player will achieve a target.
