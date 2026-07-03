# Google Cloud — maximizing the $300 free trial for ProCare

The $300 credit lasts **90 days** (whichever runs out first). Nothing auto-bills
when it ends: the account pauses until you *manually* upgrade. There is also an
**Always Free tier that survives the trial** — the plan below leans on it so the
pharmacy keeps most benefits at **$0/month after the credit is gone**.

> Rule 1: set up **budget alerts first** (Billing → Budgets → $50 / $150 / $250
> thresholds, email alerts). Five minutes that prevents every horror story.

---

## What NOT to spend it on

| Temptation | Why not |
|---|---|
| **Cloud SQL for SQL Server** | ~$70–130/month burns the credit in ~10 weeks and then bills forever. SQL Server **Express on the pharmacy PC is free forever** (see `deploy/SQL-SERVER-EXPRESS.md`). |
| Big GPU/compute experiments | Eats the credit in days, zero pharmacy value. |
| Leaving test resources running | Idle VMs/disks/IPs silently drain credit. Delete what you don't use. |

## The plan (three phases)

### Phase A — costs $0, do this week (no credit needed)

1. **Gemini API key (AI Studio free tier)** — https://aistudio.google.com →
   *Get API key*. Keys start with `AIza…`. Free tier is enough for the
   assistant's classification calls. On the pharmacy PC:
   ```bat
   setx GEMINI_API_KEY "AIza...your-key..."
   ```
   Restart ProCare — it auto-detects the key and switches the AI assistant
   from the offline router to Gemini. **Never put the key in git.**
2. **Budget alerts** (see above) on the billing account.

### Phase B — spend the credit where it compounds (90 days)

| Use | Service | Est. cost | What ProCare gains |
|---|---|---|---|
| **Off-site nightly backups** | Cloud Storage (Coldline) | ~$0.10–0.50/mo | The `.bak` from the nightly SQL Server backup uploaded off-site — fire/theft/disk-death insurance. `gsutil cp C:\Backups\ProCare.bak gs://procare-backups/` as step 2 of the same scheduled task. |
| **Cloud VM as online mirror** (optional) | Compute Engine **e2-micro** (us-west1/us-central1/us-east1) | **$0 — Always Free** | A tiny always-on Linux VM running the Docker stack as a read-only online mirror/staging copy. Survives the trial at $0. (1 GB RAM — enough for backend+frontend, not SQL Server; use SQLite there.) |
| **Better AI throughput** | Vertex AI (Gemini paid tier, billed against credit) | pennies per 1k requests | If the free AI-Studio quota ever throttles busy hours, point the key at paid tier during the trial and measure real monthly cost (likely < $2/mo at pharmacy volume). |
| **Uptime check** | Cloud Monitoring | $0 (free allotment) | Pings your Cloudflare-tunnel URL every 5 min, emails you if the pharmacy server is down. |

Realistic burn: **$5–15 of the $300 in 90 days.** That's success, not failure —
the credit is a safety net while you wire up backups + monitoring, not a target.

### Phase C — after the trial (day 91)

Keep (all $0): e2-micro VM (Always Free), AI Studio Gemini key (free tier),
Cloud Monitoring pings (free allotment). Decide with data: if Vertex AI
metered pennies/month and you want it, upgrade billing knowingly; otherwise
drop back to the free AI Studio key. Backups at Coldline prices are ~$0.01/GB/mo
— effectively free; keep them.

## Explicitly rejected alternatives

* **Hosting ProCare's production DB in the cloud** — the pharmacy must keep
  selling when the internet is down. Production stays on the local PC;
  the cloud is for backups, monitoring, AI, and an optional mirror.
* **Cloud Run for the backend** — needs the DB near it (see above). Fine for
  a demo, wrong for the POS.

## Security notes

* API keys and tunnel tokens live in **environment variables / .env only** —
  never in git, never in chat, never in screenshots. If a key leaks, revoke it
  (AI Studio → API keys → delete) and issue a new one.
* Give the backup upload its own **service account** with write-only access to
  the one bucket (`roles/storage.objectCreator`), nothing else.
