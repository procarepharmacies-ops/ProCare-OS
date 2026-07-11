# Progress Log (B.L.A.S.T.)

## 2026-07-10 → 07-11 · Phase 0 (merged)
- 7 feature areas built, tested, merged to main (PRs #13–#15): Windows 500 fix,
  LLM registry, WhatsApp automation, substitutions+transfers, prescriptions
  flow, daily ops tasks, dashboard drill-down, eStock connector script.
- pytest suite green; `next build` clean at merge time.
- CLAUDE.md merged with operating charter (owner-approved, conflict resolved
  with --theirs on the pharmacy PC).

## 2026-07-11 · Phase 1 (in flight)
- Owner feedback after first real use: search weak (wants prefix suggestions),
  drill-down "not working" on pharmacy PC, and جرد screens missing (full count,
  periodic count, item adjustment) — wants eStock-style screens with reports.
- DONE (uncommitted, on claude/arabic-display-data-sync-ukdieq):
  - Prefix-first search ranking in `services/inventory.py::list_products`.
  - POS: Enter-to-add-top-match + live match-count hint.
  - Models `StockCount`/`StockCountLine` appended to `db/models.py`.
  - `services/stocktaking.py` (create/list/get/record/post/cancel/top_movers).
  - `api/stocktaking.py` + registration in `api/routes.py`.
- Blueprint approved (owner said continue; recommended defaults adopted:
  table-entry count sheet, manager/CEO-only posting, fail-soft keys).
- ERROR + FIX (self-annealing): test_sync failed — the eStock mirror wipes
  products/stock_batches every cycle, and جرد FKs onto them blocked the wipe
  and would lose history in production. Fix: no FKs from count lines onto
  mirror-wiped tables; snapshot name_ar; outer-join sheet; posting skips
  vanished batches. Rule recorded in findings.md.
- Tests: 160/160 pass (5 new جرد tests incl. API flow + search ranking).
- Frontend: /stocktaking page (sessions → count sheet → variance → post),
  nav + 30 i18n keys (AR/EN); `next build` clean.
- Runtime smoke test: health ok · insight payload ok · Arabic prefix search
  ("ف" → فاركولين/فلاجيل/فولتارين first) · periodic جرد created 47 lines.
- Drill-down verdict: backend + UI fine in this build — pharmacy PC needs
  `git pull` + `npm run build` (stale build), not a code fix.
