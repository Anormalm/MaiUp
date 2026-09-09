# MaiUp Architecture

## Goals

MaiUp is a local-first, auditable recommendation system for maimai DX International. It separates verified facts, community metadata, player observations, model estimates, and presentation text so uncertain evidence cannot silently become a factual claim.

## Repository layout

```text
apps/
  api/        FastAPI, SQLAlchemy, OCR, Rating, catalog, and recommendation services
  web/        React and vinext user interface
data/
  catalog/    ignored raw snapshots and tracked placeholders
  config/     International version configuration
  imports/    ignored temporary player imports
  overrides/  reviewed regional constant overrides
docs/         public English documentation and ignored local research drafts
```

## Core boundaries

### Catalog

External catalog responses never write directly into active domain tables. A synchronization run fetches the source, stores it by content hash, validates schema and domain invariants, normalizes snapshot-scoped records, and publishes only an accepted snapshot.

Every recommendation references a catalog snapshot and algorithm version so historical results remain reproducible.

### Rating

Rating calculations are pure functions using `Decimal`. The module owns coefficient thresholds, flooring, the Achievement cap, AP/AP+ bonuses, version buckets, and replacement thresholds. OCR and recommendation services call this module rather than duplicating arithmetic.

### Imports

Import metadata and normalized entries are stored separately from temporary source images. B50 imports move through explicit processing, review, and confirmed states. Confirmation requires 50 consistent entries, and confirmed imports are immutable.

Images are stripped of EXIF and original filenames, stored under random identifiers, and excluded from Git. Logs must not contain image contents or player credentials.

### Recommendations

The recommender receives confirmed observations and catalog facts and returns structured fields:

- deterministic target Achievement and chart Rating;
- deterministic conditional gain against the current bucket threshold;
- demonstrated-target evidence from the same or nearby constants;
- small-sample-shrunk personal chart-element signals;
- DXRating community difficulty signals;
- explicit provenance and limitations.

Presentation code may explain these fields but must not invent reasons or probabilities.

## Main data entities

- `catalog_snapshots`: immutable source identity and validation report;
- `songs`, `charts`, `chart_revisions`: stable chart identity and version facts;
- `chart_constants`: source/region/version values with confidence and derivation;
- `tags`, `chart_tags`: community chart metadata;
- `player_imports`, `import_entries`: confirmed player observations;
- `score_exports`: normalized mai-tools score snapshots, source declarations and unresolved rows;
- future `recommendation_runs`: inputs, algorithm version, candidates, and explanations.

Raw observations and derived recommendations remain separate. Updating a catalog or algorithm never rewrites historical imports.

## OCR workflow

```text
upload
  -> validate media type and pixel limits
  -> decode locally and strip metadata
  -> detect B35/B15 card regions
  -> OCR text and numeric fields
  -> match catalog candidates
  -> reconcile displayed Rating with exact calculations
  -> route uncertain fields to review
  -> confirm an immutable 50-entry import
```

Color is supporting evidence only. Green FC/FC+ markers are recognized, blue Sync markers are ignored, and unknown templates or inconsistent totals remain in review.

## Recommendation workflow

```text
confirmed B50
  -> build B35/B15 thresholds
  -> estimate demonstrated targets by constant
  -> estimate relative chart-element strengths
  -> generate outside-B50 candidates
  -> remove risky and unsupported candidates
  -> rank personalized candidates
  -> add labeled comfort-range fallbacks
  -> cap repeated constants
  -> return facts, evidence, source, and caveats
```

Current B50 entries are analyzed together instead of repeated as large recommendation cards. A candidate outside B50 may have been played before; only broader score data can resolve that distinction.

## Complete score import

The broader-data implementation accepts mai-tools' completed table automatically
through a userscript/bookmarklet window bridge, or by manual paste, from an
International player's authenticated official-site browser. It retains every
exported row in `score_exports`, matches exact chart identities against the pinned
catalog, and derives B35/B15 in `import_entries`. Region is declared by the player;
coverage is `exported_scores`, not guaranteed complete play history.

The bridge checks the official origin, expected window and a per-run nonce;
fully matched automatic imports are confirmed and display mai-tools recommended
levels locally. Unmatched rows remain visible and block confirmation. Corrections require a new
import; confirmed snapshots remain immutable. The existing recommender continues
to use only a full B35/B15. See [the import guide](mai-tools-import.en.md) for the
format, endpoints, limits, data provenance, and manual validation procedure.

## API principles

- Write operations use stable error codes and idempotency where appropriate.
- Long OCR tasks expose progress instead of holding an unbounded request.
- OpenAPI is the contract source for frontend types.
- Inputs are size-limited and validated by content rather than filename.
- APIs do not accept SEGA passwords or persistent session cookies.
- Recommendation responses identify catalog snapshot, source, algorithm version, and evidence limitations.

## Privacy and security

- Anonymous local use does not require an account.
- Player images, score databases, and raw catalog snapshots are excluded from Git.
- Raw images are temporary and deletable.
- Logs contain identifiers, stages, error codes, and timing only.
- Player data never enters fixtures without explicit anonymization and consent.
- Any remote deployment requires a retention policy, encrypted transport, rate limits, secret management, and a new threat-model review.

## Validation strategy

### Rating

- exact coefficient-boundary tests;
- flooring and 100.5% cap tests;
- AP/AP+ bonus tests;
- B35/B15 version-membership tests;
- real International B50 reconciliation.

### Catalog

- schema and source-hash tests;
- stable identity and duplicate tests;
- region/version/constant conflict reports;
- safe fallback when refresh fails.

### OCR

- malicious and oversized image rejection;
- field accuracy by supported template;
- full-image consistency checks;
- review and immutable-confirmation tests;
- retention and deletion tests.

### Recommendations

- deterministic output for identical snapshots and algorithm versions;
- no claim that outside-B50 means unplayed;
- no probability label for descriptive evidence;
- small-sample shrinkage and comfort-range tests;
- correct DXRating water/risky tag semantics;
- candidate diversity and dynamic threshold tests.

## Release discipline

Development uses small, reviewable commits. Source, release artifacts, and runtime data remain separate. Commits must never contain databases, raw catalog snapshots, B50 images, OCR exports, environment files, generated builds, or dependencies.
