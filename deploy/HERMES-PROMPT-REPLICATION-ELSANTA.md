# Hermes prompt — fix eStock replication (run on the ELSANTA PC)

Paste everything below the line into Hermes Agent on the Elsanta PC.

---

You are on the ELSANTA pharmacy PC (expected: computer DESKTOP-DUTL25M, LAN 192.168.1.9,
public IP 196.202.93.37). SQL Server 2008, eStock database name: `stock`. The ProCare database
(`ProCare`) is on the same SQL instance.

PROBLEM: eStock replication Mashala -> Elsanta is stopped. In `stock.dbo.Branches` the Mashala
row (branch_id 2, branch_ip1 196.202.93.36) has every replication watermark frozen at
2026-06-01; Elsanta's own row (branch_id 1) is current. Both rows were edited on 2026-06-08.
Also: `stock` is FULL recovery with log_reuse_wait LOG_BACKUP and a 17 GB log for 1.2 GB of
data; `ProCare` data is ~18 GB (a duplicate-per-sync bug, fixed in commit f6a9d81 on branch
claude/hopeful-clarke-azcpi7, not yet deployed here).

RULES (hard):
- Read-only on `stock` unless the owner explicitly says "yes" to one specific statement shown to
  them first. Never touch rep_* watermark columns. No DROP/TRUNCATE/DELETE in `stock`.
- Before ANY write to `stock`: take a fresh full backup and verify it:
  `BACKUP DATABASE stock TO DISK = N'F:\backup\stock_before_fix.bak' WITH INIT, CHECKSUM;`
  `RESTORE VERIFYONLY FROM DISK = N'F:\backup\stock_before_fix.bak' WITH CHECKSUM;`
- Never open TCP 1433 to the whole internet; any firewall rule is scoped to remote IP
  196.202.93.36 only. Do not change the router; tell the owner what to change.
- Before ANY change (service, firewall, SQL statement), show the exact command and wait for
  "yes". Log every command and its output. Never print or send passwords.

STEPS:
1. In the ProCare-OS folder: `git fetch origin claude/hopeful-clarke-azcpi7`,
   `git checkout claude/hopeful-clarke-azcpi7`, then run
   `deploy\ProCare-Replication-Check.bat elsanta`. Read `ProCare-replication-elsanta.txt`.
2. Reach Mashala: the file has the TCP test to 196.202.93.36:1433. If CLOSED: run it again, then
   `ping 196.202.93.36` and `tracert -d 196.202.93.36`, and report. Ask the Mashala PC (Hermes
   prompt for Mashala) for its current public IP.
3. If Mashala's public IP is NOT 196.202.93.36 any more, the Mashala row still points to the old
   address. Propose (backup first, owner "yes" first) ONLY:
   `UPDATE stock.dbo.Branches SET branch_ip1 = '<new Mashala public IP>' WHERE branch_id = 2;`
   Show the row before and after. Change nothing else in that row.
4. eStock replication program on this PC: find it (`tasklist | findstr /i "stock"`,
   `schtasks /query /fo LIST | findstr /i "stock"`, Startup folder). If not running, propose
   starting it (owner "yes" first).
5. Firewall on this PC: `netsh advfirewall firewall show rule name=all | findstr /i 1433`. If an
   inbound allow from Mashala is missing, propose:
   `netsh advfirewall firewall add rule name="eStock SQL from Mashala" dir=in action=allow protocol=TCP localport=1433 remoteip=196.202.93.36`
6. Disk/log: from the check file, report free space per drive and the `stock` log size.
   HOLD: do NOT back up, shrink or change the recovery model of the `stock` log while a
   deleted product (Panadol) is being recovered from it (sql/find-product-delete-in-log.sql). If a
   drive is under 10% free, say so first. For the 17 GB `stock` log follow
   `sql\stock-log-maintenance.sql` Section 1 (read-only); only with the owner's "yes" use
   Option A (log backup + one shrink). Never Option B without the owner choosing it.
7. Deploy the ProCare fix: restart the ProCare backend (it already runs this branch after
   step 1), check `http://localhost:8100/api/health` returns status ok and
   `/api/sync/status` shows a recent run. After one sync cycle, run in SSMS:
   `SELECT COUNT(*), COUNT(DISTINCT source_order_id) FROM ProCare.dbo.branch_order_headers;`
   The two numbers should now be close (duplicates purged).
8. VERIFY replication: after the fix, every 15 minutes for 1 hour run
   `SELECT branch_id, rep_sales_date, rep_purchase_date, rep_shortcoming_date FROM stock.dbo.Branches;`
   Mashala's dates must move past 2026-06-01. If they do not move, report it as NOT fixed.

REPORT to the owner in Arabic: root cause, what you changed (commands + output), proof from
step 8 (before/after dates), what is still blocked and who must do it, and attach
`ProCare-replication-elsanta.txt`.
