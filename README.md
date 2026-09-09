# MaiUp

MaiUp is a local-first score analysis and personalized song recommendation tool for **maimai DX International Version**. It currently focuses on traceable catalog data, version-aware Rating calculations, reviewable B50 image recognition, and explainable score-improvement recommendations.

## Current status

- **Official-site score import:** a userscript or bookmarklet automatically fetches International scores with mai-tools and transfers them to local MaiUp. Manual clipboard import remains available. All exported rows are retained, unresolved matches are reported, and B35/B15 uses the pinned catalog. See [the import guide](docs/mai-tools-import.en.md).
- **mai-tools recommended levels:** embedded SS/SS+/SSS/SSS+ target tables use the upstream algorithm to exceed each B35/B15 cutoff. These appear beside MaiUp's existing personalized recommendations.
- **Catalog:** synchronizes International songs and charts from the public DXRating catalog, stores immutable source snapshots by content hash, validates them, and only publishes accepted snapshots to SQLite.
- **Rating engine:** uses `Decimal` arithmetic for coefficient boundaries, flooring, the 100.5% cap, AP/AP+ bonuses, and dynamic B35/B15 construction. The B15 window is derived from the configured current version rather than hard-coded version names.
- **B50 import:** accepts PNG/JPEG images and runs RapidOCR locally. It matches title, Achievement, rank, displayed chart constant, chart Rating, FC/FC+, chart type, difficulty, and B35/B15 position. Blue Sync markers are intentionally ignored.
- **Review workflow:** low-confidence fields remain editable and all 50 entries must be confirmed before analysis. Confirmed imports are immutable.
- **Experimental recommendations:** `b50-personal-fit-v0.6` first checks whether the player has demonstrated the target Achievement at the same or a nearby chart constant. It then prioritizes matching chart elements, conditional Rating gain, and DXRating community difficulty signals.
- **Community difficulty tags:** DXRating `Overrated` is treated as a positive “water chart” signal. `Underrated` is treated as a risky or deceptively difficult chart signal and excluded from ordinary score-improvement recommendations.
- **Recommendation focus:** the page prioritizes charts outside the current B50, with up to ten candidates per bucket. Existing B50 entries are used as combined evidence for comfort range, target attainment, and chart-element analysis rather than repeated as full recommendation cards.

Calibrated success probabilities, objective chart-difficulty ordering, and dynamic `+10 Rating` plans remain disabled until complete score histories or a larger real-world validation set are available.

## Data snapshot and limitations

The local catalog snapshot synchronized on 2026-09-09 contains 1,769 source songs, including 1,534 International songs and 6,305 International charts, with zero validation errors and zero warnings. The current configured version is CiRCLE PLUS, so the B15 window is `CiRCLE + CiRCLE PLUS`. Future version changes only require updating `data/config/international.json`.

DXRating does not currently expose a separate authoritative International chart-constant field. The 6,305 local constants are therefore marked `community_base_fallback` with confidence `0.750`. Verified regional corrections may be added to `data/overrides/international_chart_constants.json`. These values must not be presented as official SEGA International constants.

Community tags are weak evidence supplied by DXRating users. They are useful for explanation and ranking, but they are not objective chart classifications or guaranteed difficulty labels.

## Privacy

- Image processing and OCR run locally.
- Uploaded images have EXIF metadata and original filenames removed after decoding.
- Temporary imports use random IDs under `data/imports/` and are excluded from Git.
- Local databases, raw catalog snapshots, uploaded images, OCR output, and environment files are excluded by `.gitignore`.
- The current application does not accept or store SEGA IDs, passwords, or session cookies.
- mai-tools runs in the player's authenticated official-site browser; only the requested score export is transferred to local MaiUp, automatically or by paste. Manual exports use a declared region; automatic transfers additionally validate the official browser origin. Missing rows are not treated as unplayed charts.

## Run locally

Backend, in PowerShell:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m app.jobs.sync_catalog
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in another PowerShell window:

```powershell
cd apps/web
npm.cmd run dev
```

Open `http://localhost:3000/`. API documentation is available at `http://127.0.0.1:8000/docs`.

## Validation

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m pytest

cd ..\web
npx.cmd oxlint app types
npm.cmd run build
```

Current automated validation: **52 backend tests pass**, the application-owned frontend code passes targeted linting, and the production frontend build succeeds. The scaffold still contains unused shadcn components with upstream accessibility lint findings, so a full-directory `npm run lint` is not yet green.

## Real-image validation

The saved JiETNG International B50 fixture currently matches all 50 entries, reproduces the displayed total Rating of 15,150, and identifies 25 green FC markers. This validates one known template only; it does not yet establish compatibility with every resolution, template variant, or AP/AP+ case.

Recommended manual checks for a new image:

1. Prepare a current International B50 overview image and optionally redact the player name and avatar.
2. Upload it from the home page and wait for the local OCR review page.
3. Verify the automatic-read count, all 50 chart matches, and green FC/FC+ markers.
4. Report repeated low-confidence patterns with a review-page screenshot so the relevant OCR region can be calibrated.

## Documentation

- [`docs/research.en.md`](docs/research.en.md): source evaluation, International rules, data-access constraints, and recommendation research.
- [`docs/architecture.en.md`](docs/architecture.en.md): system boundaries, data model, OCR workflow, recommendation model, privacy, and validation gates.

## Project scope

MaiUp is an independent community project and is not affiliated with or endorsed by SEGA. Catalog constants and chart tags are community-maintained unless explicitly identified otherwise.
