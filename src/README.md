# src/ — Application source (scaffold)

This is where ProCare OS code lives. It's intentionally a scaffold — the design is locked in
[`../docs/`](../docs) first; code fills in per the [roadmap](../docs/06-roadmap.md).

## Planned layout

```
src/
├── backend/                 # Python + FastAPI
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint
│   │   ├── config.py        # loads ../../config/connections.json
│   │   ├── db/              # SQLAlchemy engines: procare (rw), estock (ro), titan (ro)
│   │   ├── modules/         # sales, inventory, purchasing, customers, vendors,
│   │   │                    #   hr, accounts, branches, reports
│   │   ├── etl/             # mirror eStock + Titan -> ProCare DB; reconciliation jobs
│   │   ├── ai/              # PharmacyAI: chat (Arabic->safe SQL), forecast, insights
│   │   ├── automation/      # PharmacyAutomation: reorder, expiry alerts, reports (APScheduler)
│   │   ├── drugs/           # Titan/Drug-Eye: interactions, substitution, dosing
│   │   └── notify/          # WhatsApp + email
│   └── requirements.txt
│
└── frontend/                # React / Next.js (RTL, i18n ar/en, light/dark)
    ├── app/                 # routes mirroring the 9 modules
    ├── components/
    ├── i18n/                # ar.json (default), en.json
    └── theme/               # light (default) + dark tokens
```

## Build order (see roadmap)

1. **Phase 0** — backend skeleton + `config.py` reading `connections.json`; create ProCare DB from
   [`../sql/procare-schema.sql`](../sql/procare-schema.sql); frontend skeleton with language + theme toggles.
2. **Phase 1** — `etl/` initial load + incremental sync + reconciliation; read-only dashboard, AI
   assistant, expiry/low-stock alerts, drug lookup.
3. **Phase 2** — POS write path (`sp_create_sale`), pilot on Elsanta.
4. **Phase 3** — both branches on ProCare; eStock retired.

## Principles
- ProCare DB is the system of record; **eStock and Titan are read-only sources** (transition only).
- All strings externalized for ar/en. Arabic + light are defaults; English + dark are toggles.
- Secrets only in `config/connections.json` (git-ignored).
