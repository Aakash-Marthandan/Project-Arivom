import postgres from "postgres";

/**
 * Server-side Postgres client (see docs/DECISIONS.md D-002).
 * Works identically against local Postgres and hosted Supabase (pooler URL).
 * Reads only in M1; all writes happen in /pipelines.
 */
declare global {
  var __arivomSql: ReturnType<typeof postgres> | undefined;
}

function createClient() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set");
  }
  return postgres(url, {
    max: 4,
    idle_timeout: 20,
    connect_timeout: 10,
  });
}

// Reuse the pool across HMR reloads in dev.
export const sql = globalThis.__arivomSql ?? createClient();
if (process.env.NODE_ENV !== "production") {
  globalThis.__arivomSql = sql;
}
