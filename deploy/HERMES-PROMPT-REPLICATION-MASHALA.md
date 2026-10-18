# Hermes prompt — fix eStock replication (run on the MASHALA PC)

Paste everything below the line into Hermes Agent on the Mashala PC.

---

You are on the MASHALA pharmacy PC (expected: computer DESKTOP-SHTFS3J, LAN 192.168.1.2,
public IP 196.202.93.36). SQL Server 2008, eStock database name: `stock`.

PROBLEM: eStock replication Mashala -> Elsanta is stopped. On Elsanta's `stock.dbo.Branches`,
the Mashala row (branch_id 2, branch_ip1 196.202.93.36) has every replication watermark frozen
at 2026-06-01 (sales, purchases, shortcomings, cash close). Both Branches rows were edited on
2026-06-08. Elsanta is at public IP 196.202.93.37. Most likely cause: the link between the two
SQL Servers broke around 1-8 June (public IP change, router port-forward, firewall, SQL service
or eStock replication program not running).

RULES (hard):
- Never edit, insert or delete anything in the `stock` database. No UPDATE on Branches / rep_*,
  no shrink, no recovery-model change, no DROP/TRUNCATE. Read-only SELECTs only.
- Never open TCP 1433 to the whole internet. Any firewall rule must be scoped to remote IP
  196.202.93.37 only.
- Before ANY change on this PC (service start/config, firewall rule), show the owner the exact
  command and wait for "yes". Log every command you run and its output.
- Never print or send passwords/connection strings.

STEPS:
1. In the ProCare-OS folder: `git fetch origin claude/hopeful-clarke-azcpi7` then
   `git checkout claude/hopeful-clarke-azcpi7` then run
   `deploy\ProCare-Replication-Check.bat mashala`. Read `ProCare-replication-mashala.txt`.
2. Public IP: is it still 196.202.93.36? If not, record the new IP (Elsanta must be told).
3. SQL Server: `sc query state= all | findstr /i "SQL"` — the engine service must be RUNNING and
   start type AUTO. `netstat -ano | findstr :1433` — must show LISTENING. If TCP/IP is disabled
   in SQL Server Configuration Manager, report it (do not change protocols yourself).
4. Firewall: `netsh advfirewall firewall show rule name=all | findstr /i 1433` — is there an
   inbound allow for TCP 1433? If missing, propose (owner "yes" first):
   `netsh advfirewall firewall add rule name="eStock SQL from Elsanta" dir=in action=allow protocol=TCP localport=1433 remoteip=196.202.93.37`
5. Reach Elsanta: the check file has the TCP test to 196.202.93.37:1433. If CLOSED, the problem
   is on the Elsanta side or the internet path; report it.
6. eStock replication program: find it (`tasklist | findstr /i "stock"`,
   `schtasks /query /fo LIST | findstr /i "stock"`, Startup folder). If it is not running,
   propose starting it (owner "yes" first) and confirm it stays up.
7. Router: if the public IP is right, the service listens and the firewall allows 1433, but
   Elsanta still cannot connect, the router port-forward is missing. Do NOT change the router;
   tell the owner exactly: "forward WAN TCP 1433 -> 192.168.1.2:1433, allowed source
   196.202.93.37 only".
8. Disk: `wmic logicaldisk get caption,freespace,size` and confirm H:\backup has a .bak from the
   last hour. Report if any drive is under 10% free.

REPORT to the owner in Arabic: what was wrong, what you changed (commands + output), what is
still blocked and who must do it (Elsanta side / router / ISP), and attach
`ProCare-replication-mashala.txt`.
