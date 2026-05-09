#!/usr/bin/env tsx
/**
 * Validates a room descriptor JSON file against spec/room.schema.json.
 *
 * Usage:
 *   pnpm validate:spec
 *   tsx tools/validate-spec.ts spec/teahouse.room.json
 *
 * Exits 0 on success, 1 on validation error.
 */
import { readFileSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");

const targetArg = process.argv[2] ?? "spec/teahouse.room.json";
const target = resolve(repoRoot, targetArg);
const schemaPath = join(repoRoot, "spec", "room.schema.json");

function loadJson(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf8"));
}

const schema = loadJson(schemaPath) as Record<string, unknown>;
const data = loadJson(target);

const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validate = ajv.compile(schema);
const ok = validate(data);

if (!ok) {
  console.error(`spec validation FAILED for ${targetArg}:`);
  for (const err of validate.errors ?? []) {
    const path = err.instancePath || "(root)";
    console.error(`  ${path}: ${err.message}`);
    if (err.params) {
      console.error(`    params: ${JSON.stringify(err.params)}`);
    }
  }
  process.exit(1);
}

const room = data as { id?: string; name?: string; spawnPoints?: unknown[] };
console.log(`spec validation OK: ${targetArg}`);
console.log(`  id=${room.id} name="${room.name}"`);
console.log(`  spawnPoints=${room.spawnPoints?.length ?? 0}`);
