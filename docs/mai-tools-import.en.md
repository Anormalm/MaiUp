# Automatically sync official-site scores with mai-tools

MaiUp accepts the tab-separated clipboard table produced by
[mai-tools score download](https://github.com/myjian/mai-tools/blob/1d1ce89b76950816845e5f82707ab108ae35d0a0/src/scripts/score-download.ts).
The player runs mai-tools in their authenticated browser on maimai DX NET. A
MaiUp userscript or bookmarklet transfers the completed export directly into the
local app. Manual paste remains available. MaiUp does not log into SEGA, request
credentials, or fetch account pages on its backend.

## Automatic workflow

1. Open <http://localhost:3000/sync> in the same browser where you log into
   maimai DX NET. Keep MaiUp's local API running on `127.0.0.1:8000`.
2. Install a userscript manager such as Tampermonkey once, then click **安装 MaiUp 助手**
   on the sync page and install/enable it in the manager. If the browser downloads
   or displays the script, import the downloaded file into the manager instead.
   Allow the extension to execute userscripts if your browser requires it.
   It runs only on the International home page when a
   MaiUp sync was explicitly requested; it does not run on a schedule.
3. Sign into your own International account. Click **一键导入官网成绩**
   in MaiUp. The helper runs the published mai-tools score-download script,
   includes all export fields, triggers fetching, and transfers only a completed
   table back to MaiUp. No bookmark click in the official tab is needed. Keep both tabs open.
4. Fully matched imports are automatically confirmed and open the score page,
   including the embedded mai-tools recommended-level tables. Unmatched rows
   remain visible and block confirmation.

Without a userscript manager, use **复制自动同步书签**, save the generated code as
a bookmark's URL, then click that bookmark on your logged-in official home page.
This opens the local receiver and automates fetching/import without copy/paste.
Allow the local tab to open if your browser blocks it.

The sync page provides a draggable **MaiUp 自动同步** bookmark. This is different
from the original all-in-one mai-tools bookmarklet: only the MaiUp helper sends
the finished export back to the local app. A missing helper is reported after
ten seconds, with setup guidance, instead of being described as a score-fetch
timeout. The connection remains available briefly so you can run the bookmark
in the already-open official tab. The local API/catalog is checked before that
tab navigates to the official site.

The helper cannot log in for you. If a login redirect loses the connection,
finish signing in and start sync again. Use the same browser for both windows;
a separate in-app browser cannot share an ordinary browser's window connection.
If the in-app browser does not support userscript extensions, open localhost in
the browser where the manager and your official login are available.

The directly installable `/maiup-sync.user.js` is generated from `/maiup-sync.js`
by `scripts/build-sync-userscript.mjs`. `npm run dev` and `npm run build` regenerate
it; the tests check that the committed installable file matches the bridge source.
After updating a locally installed helper, reinstall it from the sync page.

### Transfer behavior

`postMessage` connects the two browser windows, so no credentialed official-site
request is made from localhost and no official-origin CORS access is added to
the API. The receiver checks the exact official origin, expected window,
protocol version, random per-run nonce, message type and payload size. Scores
never travel in URLs. The helper accepts only the two existing loopback frontend
origins, and runs only on the player's International home page. There are bounded
timeouts, cancellation, upstream completion checks and duplicate-message guards.

Cancelling stops the transfer; an already-running upstream fetch may complete in
the official tab. The one-time helper setup and manual login remain necessary.

## Manual clipboard fallback

1. Start the local API and frontend and synchronize the International catalog.
2. Log into your account at <https://maimaidx-eng.com/maimai-mobile/>.
3. Run the [mai-tools bookmarklet](https://myjian.github.io/mai-tools/#howto).
   MaiUp's **完整成绩** tab also offers a button to copy its loader. Loading the
   bookmarklet opens the tools; it does not automatically export scores.
4. Open score download. Include **Song**, **Chart**, **Difficulty**, **Achv**, and
   **FC/AP**. Enable **DX Score** if desired; mai-tools excludes it by default.
5. Choose **Load all scores**, wait for all difficulties to finish, then **Copy**.
   Paste the entire table, including its header, into MaiUp.
6. Confirm that the export came from your own International account. Import and
   inspect the score pages and calculated B35/B15 before confirming.

English, Traditional Chinese, and Korean headers are accepted, with optional
columns in any order. No spreadsheet conversion is needed. A synthetic example:

```text
Song	Chart	Difficulty	Achv	FC/AP
Example song	DX	MASTER	100.5000%	AP+
```

Replace the example title with a real catalog title. Unknown or ambiguous charts
remain stored and visible with their original row numbers. Confirmation is
blocked until the source table is corrected or the catalog updated and the table
reimported. Do not discard unmatched rows to bypass review: they may belong in
B50. A new import never overwrites an earlier confirmed snapshot.

## Data and calculation boundaries

- Only International is supported. The table carries no origin marker; region is
  a player declaration, not independently verified. Japanese data cannot safely
  be interpreted using the International catalog.
- This is a current score snapshot, not individual play history, an account
  profile, or proof every chart was fetched. Coverage is `exported_scores`;
  omitted charts are not labeled unplayed.
- All accepted rows and included optional metadata (genre, exported version,
  level, constant, rank, Sync, DX Score, percentage and stars) are stored locally.
  Optional metadata remains text, not authoritative catalog data.
- Achievement uses `Decimal` with up to four decimal places; FC/AP is retained.
  Ratings use MaiUp's most confident constant and International version policy
  from the pinned catalog snapshot. Exported constants/versions never override it.
- Exact normalized title/alias, chart type and difficulty must identify one
  chart. Fuzzy guesses are not used; duplicates are rejected.
- The existing `build_best50` selects B35/B15 independently. The total is a
  calculation, not an official-site Rating verification.
- Fewer than 50 eligible charts may be confirmed. The experimental recommender
  still requires 35 + 15 entries and analyzes only B50. Incorporating the extra
  scores into recommendations is a separate change.
- Structured imports are corrected by reimporting. Editing their derived B50
  through the image-review API is blocked to keep it consistent with the export.

## API and persistence

`POST /v1/imports/mai-tools` accepts:

```json
{
  "sourceOrigin": "https://maimaidx-eng.com",
  "scoreText": "Song\tChart\tDifficulty\tAchv\tFC/AP\nExample song\tDX\tMASTER\t100.5000%\tAP+"
}
```

The response extends the normal import response with `sourceOrigin`, `scores`,
and `issues`. Retrieve it with `GET /v1/imports/{id}/scores`. The existing
`POST /v1/imports/{id}/confirm` locks a fully matched import. Limits are 2 MB UTF-8,
10,000 rows, and the known mai-tools columns. Malformed input is rejected before
persistence; unmatched but well-formed rows remain reviewable.

The additive `score_exports` table stores the source declaration and normalized
records/issues as JSON linked to `player_imports`. Derived B50 rows use
`import_entries`. No existing columns change: startup's `Base.metadata.create_all`
creates the new table. Restart the API after updating. Databases stay out of Git.

## Validation and upstream dependency

Matching uses the exported genre to distinguish songs sharing a title, including
the two songs named `Link`. The official `niconico＆VOCALOID™` category maps to
DXRating's `niconico＆ボーカロイド`; missing or unrecognized genres never select
an arbitrary candidate. Blank song names are legitimate and matched to the catalog.

Catalog region flags can lag behind the game. Reviewed corrections live in
`data/overrides/international_availability.json`, with chart identities, displayed
levels, public evidence URLs and verification dates. Catalog sync includes applied
corrections in the archived JSON and content hash, without changing constants.
When upstream supplies International availability, its regional data takes precedence.
The current correction covers the four DX charts of `魔理沙は大変なものを盗んでいきました`,
verified against SEGA's International song-list JSON on 2026-09-10. Run catalog sync
after updating this file; existing imports retain their original snapshot and need
reimporting to use the correction. Never infer availability or constants from a
missing match alone.

Backend synthetic tests cover localized/reordered headers, optional metadata, malformed
and oversized inputs, ambiguous/missing charts, alias duplicates, catalog
provenance, AP+, preserving more than 50 scores, independent bucket selection,
confirmation gates, and the API round trip.

`npm test` in `apps/web` checks the bridge protocol and mocked browser lifecycle:
origin/window/nonce guards, incomplete exports, one fetch per run, all included
fields, cancellation, popup/login/upstream failures, and timeouts. It also checks
the upstream recommended-level calculations. These are synthetic tests, not an
authenticated browser end-to-end test.

A real International export still needs manual validation: compare imported row
count, chart matches, Achievement/FC/AP, and B50 with the original. Do not commit
real player data. These fixtures do not test authenticated official-site fetching.
mai-tools is independently maintained and may need updates when the site changes.

## Embedded recommended levels

The score review and recommendation pages now show mai-tools' actual
`calcRecommendedLevels` output for SS, SS+, SSS and SSS+. Inputs are each full
MaiUp bucket's minimum Rating plus one. Incomplete buckets do not show replacement
targets; unresolved imports show a provisional warning. The table gives chart
constant, rank, required Achievement and resulting Rating, not a personalized
probability of success. MaiUp's existing recommendation algorithm remains available.

The vendored calculation keeps upstream floating-point rounding, excludes AP
bonuses from the proposed targets, and intentionally omits near-rank maximum
factors as upstream does. Actual imported score ratings still use MaiUp's Decimal
calculator. These differences can make the targets conservative.

Thanks to [myjian/mai-tools](https://github.com/myjian/mai-tools). The browser
scraper is loaded externally. The two small calculation modules are vendored at
the pinned revision under `apps/web/vendor/mai-tools/`, with the upstream GNU GPL
v3 license and a notice describing the adaptations. Their source and attribution
are linked from the tables.
