#!/usr/bin/env node
/**
 * Optional helper: fetch OpenAPI from a running API and remind maintainers to sync api-types.ts.
 * The checked-in source of truth is src/lib/api-types.ts for CI stability.
 */
const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const response = await fetch(`${base}/openapi.json`);
if (!response.ok) {
  console.error(`Could not fetch OpenAPI from ${base} (${response.status}).`);
  process.exit(1);
}
const spec = await response.json();
const paths = Object.keys(spec.paths ?? {}).sort();
console.log("OpenAPI paths (sync manually to src/lib/api-types.ts if changed):");
for (const path of paths) {
  console.log(`  ${path}`);
}
