# Paste-once prompt: diagnose + fix unit-mixed balances (run on a branch PC)

Run Claude Code **on the Mashala (or Elsanta) PC**, inside the `ProCare-OS`
folder, where it can reach the LAN-only SQL Server. Cloud sessions cannot
(port 1433 is LAN-only by design, see `SQL-SERVER-2008-ELSANTA.md`).

```
cd ProCare-OS
git fetch origin claude/hopeful-clarke-azcpi7
git checkout claude/hopeful-clarke-azcpi7
claude
```

Then paste the prompt below.

---

## Prompt

Problem: on the eStock sales screen at Mashala, product code 51293
("حفاضات كبار سن ليبدو 36 قطعة") appears twice with different balances
(465.12 vs 12.92, reorder level 2592 vs 72). 465.12 / 12.92 = 2592 / 72 = 36
= the pack size, so one row shows small units and the other big units.
Goal: find out whether the SOURCE data is mixed or only the screen display,
and fix ProCare only if the data is mixed.

Rules (CLAUDE.md is law): SQL Server 2008 compatible, never write to eStock
(SELECT only), stock is always stored in BIG units, no secrets in git, tests
required, never push to main, PR only.

Steps:
1. Read `config/connections.json` (or `.env`) for the read-only eStock login.
   Do not print credentials. Run `sql/diagnose-unit-balance.sql` against the
   Mashala eStock database with a SELECT-only login. Do the same for Elsanta
   and compare. Save results to `.tmp/` (git-ignored), not the repo.
2. Report in Arabic: unit factor for 51293, the stored `Product_Amount`
   rows, and a verdict:
   - Same unit in every row -> display-only in eStock. Stop; change nothing
     in ProCare. Explain how to fix the sales-screen unit in eStock.
   - Mixed units across rows/branches -> real data issue. Continue to 3.
3. Only for the mixed case: add unit normalisation to
   `src/backend/app/services/etl.py::_load_stock` (and
   `_load_branch_product_amount`) so every amount lands in big units, using
   the product's `unit_factor`. Keep it idempotent and `has_table`/column
   guarded. Add `test_*.py` covering happy path + factor 1 + missing factor.
4. Run `pytest app/tests/` and the ETL on a COPY of the database first.
   Back up before any run that changes data. Check `/api/health` and
   `/api/sync/status` afterwards.
5. Update `progress.md` and `findings.md`, commit (`fix:` format), push to a
   feature branch and open a draft PR. Do not merge.

Stop and ask me before any step that writes to a database.
