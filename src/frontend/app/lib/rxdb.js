// IndexedDB for ProCare RX. Raw API, no wrapper library — this repo has almost
// no dependencies and an offline store is not a good reason to add one.
//
// Stores:
//   outbox     pending writes, keyed by an auto id, UNIQUE on dedupe_key
//   sheets     the last-fetched count sheet, by count_id
//   scan_index the code -> line index that lets a scan resolve with no network
//   meta       device_id and bookkeeping
//
// The unique index on dedupe_key is the important bit: re-entering a quantity
// for a line already queued OVERWRITES that record instead of appending. So the
// queue can never grow past the number of distinct lines touched, fixing a typo
// three times still sends one request, and last-write-wins is settled on the
// device before the network is ever involved.

const DB_NAME = "procare-rx";
const DB_VERSION = 1;

let dbPromise = null;

export function dbAvailable() {
  return typeof indexedDB !== "undefined";
}

function openDb() {
  if (!dbAvailable()) return Promise.reject(new Error("indexeddb-unavailable"));
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("outbox")) {
        const outbox = db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
        outbox.createIndex("by_dedupe", "dedupe_key", { unique: true });
        outbox.createIndex("by_state", "state");
        outbox.createIndex("by_count", "count_id");
      }
      if (!db.objectStoreNames.contains("sheets")) {
        db.createObjectStore("sheets", { keyPath: "count_id" });
      }
      if (!db.objectStoreNames.contains("scan_index")) {
        db.createObjectStore("scan_index", { keyPath: "count_id" });
      }
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "k" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function tx(store, mode, fn) {
  return openDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const t = db.transaction(store, mode);
        const s = t.objectStore(store);
        let result;
        try {
          result = fn(s);
        } catch (e) {
          reject(e);
          return;
        }
        t.oncomplete = () => resolve(result?.__req ? result.__req.result : result);
        t.onerror = () => reject(t.error);
        t.onabort = () => reject(t.error);
      })
  );
}

const wrap = (req) => ({ __req: req });

// ---- generic key/value ---------------------------------------------------

export async function metaGet(k, fallback = null) {
  try {
    const row = await tx("meta", "readonly", (s) => wrap(s.get(k)));
    return row ? row.v : fallback;
  } catch {
    return fallback;
  }
}

export async function metaSet(k, v) {
  try {
    await tx("meta", "readwrite", (s) => s.put({ k, v }));
  } catch {
    /* non-fatal */
  }
}

/** Stable per-install id. Useful for support ("which phone lost the count?"). */
export async function deviceId() {
  let id = await metaGet("device_id");
  if (!id) {
    id =
      globalThis.crypto?.randomUUID?.() ||
      `dev-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
    await metaSet("device_id", id);
  }
  return id;
}

// ---- cached count data ---------------------------------------------------

export const saveSheet = (countId, sheet) =>
  tx("sheets", "readwrite", (s) =>
    s.put({ count_id: Number(countId), sheet, fetched_at: new Date().toISOString() })
  ).catch(() => {});

export const loadSheet = (countId) =>
  tx("sheets", "readonly", (s) => wrap(s.get(Number(countId))))
    .then((r) => r?.sheet || null)
    .catch(() => null);

export const saveScanIndex = (countId, index) =>
  tx("scan_index", "readwrite", (s) =>
    s.put({ count_id: Number(countId), ...index, fetched_at: new Date().toISOString() })
  ).catch(() => {});

export const loadScanIndex = (countId) =>
  tx("scan_index", "readonly", (s) => wrap(s.get(Number(countId))))
    .then((r) => r || null)
    .catch(() => null);

// ---- outbox --------------------------------------------------------------

/**
 * Queue a write, replacing any pending entry with the same dedupe_key.
 *
 * Replacing rather than appending is what keeps the queue bounded and makes
 * replay ordering irrelevant for a given line.
 */
export async function enqueue(entry) {
  const now = new Date().toISOString();
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction("outbox", "readwrite");
    const store = t.objectStore("outbox");
    const idx = store.index("by_dedupe");
    const lookup = idx.get(entry.dedupe_key);
    lookup.onsuccess = () => {
      const existing = lookup.result;
      const row = {
        ...(existing || {}),
        ...entry,
        // Keep the original queue position/attempt history, refresh the payload.
        id: existing?.id,
        created_at: existing?.created_at || now,
        updated_at: now,
        attempts: existing?.attempts || 0,
        next_attempt_at: existing?.next_attempt_at || 0,
        state: "pending", // a fresh edit re-arms a previously failed row
        last_error: null,
        last_status: null,
      };
      if (row.id === undefined) delete row.id;
      store.put(row);
    };
    lookup.onerror = () => reject(lookup.error);
    t.oncomplete = () => resolve(true);
    t.onerror = () => reject(t.error);
  });
}

export const allQueued = () =>
  tx("outbox", "readonly", (s) => wrap(s.getAll()))
    .then((rows) => rows || [])
    .catch(() => []);

export const removeQueued = (id) =>
  tx("outbox", "readwrite", (s) => s.delete(id)).catch(() => {});

export const updateQueued = (row) =>
  tx("outbox", "readwrite", (s) => s.put(row)).catch(() => {});

/** Drop every failed row for a count (the "give up on these" action). */
export async function clearFailed(countId = null) {
  const rows = await allQueued();
  const doomed = rows.filter(
    (r) => r.state === "failed" && (countId === null || Number(r.count_id) === Number(countId))
  );
  await Promise.all(doomed.map((r) => removeQueued(r.id)));
  return doomed.length;
}
