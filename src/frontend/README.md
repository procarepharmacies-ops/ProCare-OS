# ProCare OS — Frontend (Next.js)

**Phase 1 dashboard.** **Arabic / RTL** and **Light** are the defaults;
**English** and **Dark** are optional toggles, persisted per browser
(`localStorage`). The dashboard reads the live backend and renders real KPIs,
a daily-sales chart, top products, expiry / low-stock / debtor panels, and an
**Arabic AI assistant** — all with a Main / Elsanta / All branch switcher.

## Run

```bash
npm install
npm run dev        # http://localhost:3000
```

Start the backend too (`../backend` → `python run.py`) so the data loads; the
header shows a live **Online / Offline** status. Optionally copy
`.env.local.example` → `.env.local` to point at a different backend URL
(default `http://127.0.0.1:8000`).

## Structure

```
app/
  layout.js          <html dir/lang>, no-flash theme script, <Providers>
  providers.js       language + theme context, persistence, toggles
  i18n.js            ar (default) / en chrome strings
  api.js             fetch client + number/money formatters
  page.js            dashboard composition + branch-scoped data loading
  globals.css        light/dark theme tokens + component styles
  components/
    Header.js        title, branch switcher, lang/theme toggles, status
    KpiCards.js      headline KPI grid
    SalesChart.js    dependency-free SVG daily-sales chart
    Panels.js        top products / expiry / low-stock / debtor tables
    AiChat.js        Arabic assistant (shows the SQL each answer used)
```

No chart or UI libraries — the chart is hand-rolled SVG, so the dependency
footprint stays at `next` + `react`.
