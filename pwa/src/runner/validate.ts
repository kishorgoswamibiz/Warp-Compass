/**
 * Node-only Answer Log validation against `contracts/answer-log.schema.json` (draft-07).
 *
 * Kept out of `answerlog.ts` so `ajv` and `node:fs` never reach the browser bundle. Used by the
 * tests and the typed harness to prove the runner's output honours the brain↔runner contract
 * (the P5 definition of done). The brain validates the same contract on its side via `jsonschema`.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import type { AnswerLog } from "./types";

/** Locate `contracts/answer-log.schema.json` from this file (pwa/src/runner → repo root). */
export function answerLogSchemaPath(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, "..", "..", "..", "contracts", "answer-log.schema.json");
}

let _validate: ((data: unknown) => boolean) | null = null;

function getValidator() {
  if (_validate) return _validate;
  const schema = JSON.parse(readFileSync(answerLogSchemaPath(), "utf-8"));
  const ajv = new Ajv({ allErrors: true, strict: false });
  addFormats(ajv);
  _validate = ajv.compile(schema);
  return _validate;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/** Validate a built Answer Log against the contract. Returns human-readable errors. */
export function validateAnswerLog(log: AnswerLog): ValidationResult {
  const validate = getValidator();
  const valid = validate(log);
  const errors = valid
    ? []
    : ((validate as unknown as { errors?: { instancePath: string; message?: string }[] }).errors ??
        []).map((e) => `${e.instancePath || "/"} ${e.message ?? "invalid"}`);
  return { valid, errors };
}
