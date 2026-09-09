# Import official-site scores with mai-tools

MaiUp accepts the tab-separated clipboard table produced by
[mai-tools score download](https://github.com/myjian/mai-tools/blob/1d1ce89b76950816845e5f82707ab108ae35d0a0/src/scripts/score-download.ts).
The player runs mai-tools in their authenticated browser on maimai DX NET, then
explicitly pastes the resulting scores into local MaiUp. MaiUp does not log into
SEGA, request credentials, or fetch account pages.

## Player workflow

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

Synthetic tests cover localized/reordered headers, optional metadata, malformed
and oversized inputs, ambiguous/missing charts, alias duplicates, catalog
provenance, AP+, preserving more than 50 scores, independent bucket selection,
confirmation gates, and the API round trip.

A real International export still needs manual validation: compare imported row
count, chart matches, Achievement/FC/AP, and B50 with the original. Do not commit
real player data. These fixtures do not test authenticated official-site fetching.
mai-tools is independently maintained and may need updates when the site changes.

Thanks to [myjian/mai-tools](https://github.com/myjian/mai-tools) for the external
browser tool. MaiUp implements a clipboard-format adapter and does not bundle the
upstream scraper. The bookmarklet loads the published external script when run
by the player.
