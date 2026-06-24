# ProCare OS — Frontend (Next.js)

Phase-0 skeleton. **Arabic / RTL** and **Light** are the defaults; **English**
and **Dark** are optional toggles, persisted per browser (`localStorage`). The
dashboard pings the backend (`/api/health`, `/api/branches`) and shows a branch
switcher (Main / Elsanta / All).

## Run

```bash
npm install
npm run dev        # http://localhost:3000
```

Optionally copy `.env.local.example` → `.env.local` to point at a different
backend URL (default `http://127.0.0.1:8000`).

Or use the editor **Run** (preview): see [`../../.claude/launch.json`](../../.claude/launch.json),
server **`procare-frontend`**. Start **`procare-backend`** too so the status
card reads **Online**.

## Structure

```
app/
  layout.js      <html dir/lang>, no-flash theme script, <Providers>
  providers.js   language + theme context, persistence, toggles
  i18n.js        ar (default) / en chrome strings
  page.js        dashboard: branch switcher, toggles, live backend status
  globals.css    light/dark theme tokens (CSS variables)
```
