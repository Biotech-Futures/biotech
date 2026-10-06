/**
 * @file matchingConfig.ts
 * @description Types, Zod parsers and payload builders for the matching
 * scoring-weight config (MA1, apps/matching_runtime on the backend).
 *
 * The backend contract is uneven, so everything snake_case or inconsistent is
 * absorbed here and the UI only ever sees `MatchingWeights` / `MatchingConfig`:
 *
 * - Config fields are snake_case and weights arrive as decimal strings ("20.00").
 * - `active/` returns `{ data, weights, requiredTotal, defaults }` at the top
 *   level, with `weights` under different camelCase names
 *   (`countryMismatchPenalty`, `timezoneMaxPenalty`).
 * - `defaults/` returns the same defaults block, but wrapped in `{ data }`.
 *
 * Weights are never rescaled here. A saved config must total exactly
 * `requiredTotal` (100) and the backend rejects anything else, so the UI has to
 * show the admin their real total rather than a silently corrected one.
 */
import { z } from 'zod'
import { ApiError } from './apiError'
import type { ParseResult } from './adminMatching'

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** The five scoring weights, as percentages of the 100-point base score. */
export interface MatchingWeights {
  yearWeight: number
  countryMismatchWeight: number
  timezoneWeight: number
  timezoneMaxWeight: number
  sizeBonusWeight: number
}

export type MatchingWeightKey = keyof MatchingWeights

/** Display order for the weight inputs. */
export const MATCHING_WEIGHT_KEYS: readonly MatchingWeightKey[] = [
  'yearWeight',
  'countryMismatchWeight',
  'timezoneWeight',
  'timezoneMaxWeight',
  'sizeBonusWeight'
]

/** A saved weight set (one `MatchingConfig` row). */
export interface MatchingConfig {
  id: number
  name: string
  isActive: boolean
  weights: MatchingWeights
  /** Server-computed sum of `weights`. */
  totalWeight: number
  /** User id of the last admin to save it, or null. */
  updatedBy: number | null
  createdAt: string
  updatedAt: string
}

/** A complete, valid starting split for a new config. */
export interface MatchingConfigDefaults {
  weights: MatchingWeights
  /** What a saved config must total exactly — 100. */
  requiredTotal: number
}

/** What matching is scored with right now, from `GET /matching/configs/active/`. */
export interface ActiveMatchingConfig {
  /** The saved config in force, or null when none is. */
  config: MatchingConfig | null
  /**
   * The weights a run would use today. With no saved config these are the
   * built-in legacy values, which do not total `requiredTotal`.
   */
  appliedWeights: MatchingWeights
  /** True when no config is saved and the built-in weights apply. */
  usingBuiltInWeights: boolean
  defaults: MatchingConfigDefaults
}

export interface CreateMatchingConfigPayload {
  name: string
  weights: MatchingWeights
  /** Defaults to true server-side: a new config replaces the active one. */
  isActive?: boolean
}

export interface UpdateMatchingConfigPayload {
  name?: string
  /** Partial is allowed; the server checks the total against stored values. */
  weights?: Partial<MatchingWeights>
  isActive?: boolean
}

/** Validation messages from a rejected save, keyed for the form. */
export interface MatchingConfigFieldErrors {
  /** The "must total exactly 100%" message (backend `weight_total`). */
  weightTotal?: string
  name?: string
  /** Per-weight messages, e.g. out of range or too many decimal places. */
  weights: Partial<Record<MatchingWeightKey, string>>
  /** Anything not tied to a field the form shows (e.g. `non_field_errors`). */
  other: string[]
}

// ---------------------------------------------------------------------------
// Field-name mapping (the only place snake_case lives)
// ---------------------------------------------------------------------------

/** Frontend weight key -> config field on the backend serializer. */
const CONFIG_FIELD: Record<MatchingWeightKey, string> = {
  yearWeight: 'year_weight',
  countryMismatchWeight: 'country_mismatch_weight',
  timezoneWeight: 'timezone_weight',
  timezoneMaxWeight: 'timezone_max_weight',
  sizeBonusWeight: 'size_bonus_weight'
}

/**
 * Frontend weight key -> key in `active/`'s `weights` block, which comes from
 * ScoringWeights.as_dict() and names two of the weights differently.
 */
const APPLIED_WEIGHT_FIELD: Record<MatchingWeightKey, string> = {
  yearWeight: 'yearWeight',
  countryMismatchWeight: 'countryMismatchPenalty',
  timezoneWeight: 'timezoneWeight',
  timezoneMaxWeight: 'timezoneMaxPenalty',
  sizeBonusWeight: 'sizeBonusWeight'
}

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

/**
 * DRF serialises DecimalField as a string ("20.00"); the defaults and applied
 * weights arrive as plain numbers. Both become numbers. An empty or
 * non-numeric string fails rather than quietly becoming 0.
 */
const decimal = z
  .union([z.number(), z.string().trim().min(1)])
  .transform(Number)
  .pipe(z.number().finite())

/** Zod shape for the five weights under the given backend field names. */
const weightShape = (fields: Record<MatchingWeightKey, string>) =>
  Object.fromEntries(MATCHING_WEIGHT_KEYS.map((key) => [fields[key], decimal])) as Record<
    string,
    typeof decimal
  >

/** Pick the five weights out of a parsed record, under frontend names. */
const pickWeights = (
  raw: Record<string, unknown>,
  fields: Record<MatchingWeightKey, string>
): MatchingWeights =>
  Object.fromEntries(
    MATCHING_WEIGHT_KEYS.map((key) => [key, raw[fields[key]] as number])
  ) as unknown as MatchingWeights

const weightsSchema = (fields: Record<MatchingWeightKey, string>) =>
  z.object(weightShape(fields)).transform((raw) => pickWeights(raw, fields))

const configSchema = z
  .object({
    id: z.number().int().positive(),
    name: z.string(),
    is_active: z.boolean(),
    total_weight: decimal,
    updated_by: z.number().int().nullable().default(null),
    created_at: z.string(),
    updated_at: z.string(),
    ...weightShape(CONFIG_FIELD)
  })
  .transform(
    (raw): MatchingConfig => ({
      id: raw.id,
      name: raw.name,
      isActive: raw.is_active,
      weights: pickWeights(raw, CONFIG_FIELD),
      totalWeight: raw.total_weight,
      updatedBy: raw.updated_by,
      createdAt: raw.created_at,
      updatedAt: raw.updated_at
    })
  )

/** `{ requiredTotal, defaults }` — shared by `active/` and `defaults/`. */
const defaultsBlockShape = {
  requiredTotal: decimal,
  defaults: weightsSchema(CONFIG_FIELD)
}

const toDefaults = (raw: {
  requiredTotal: number
  defaults: MatchingWeights
}): MatchingConfigDefaults => ({ weights: raw.defaults, requiredTotal: raw.requiredTotal })

/** `GET defaults/` wraps the block in `data`. */
const defaultsResponseSchema = z
  .object({ data: z.object(defaultsBlockShape) })
  .transform((raw) => toDefaults(raw.data))

/** `GET active/` puts the same block at the top level, beside `data`. */
const activeResponseSchema = z
  .object({
    data: configSchema.nullable(),
    weights: weightsSchema(APPLIED_WEIGHT_FIELD),
    ...defaultsBlockShape
  })
  .transform(
    (raw): ActiveMatchingConfig => ({
      config: raw.data,
      appliedWeights: raw.weights,
      usingBuiltInWeights: raw.data === null,
      defaults: toDefaults(raw)
    })
  )

// ---------------------------------------------------------------------------
// Parse helpers
// ---------------------------------------------------------------------------

const toResult = <T>(result: z.ZodSafeParseResult<T>, label: string): ParseResult<T> =>
  result.success
    ? { ok: true, data: result.data }
    : {
        ok: false,
        message: `${label} returned an unexpected format - ${z.prettifyError(result.error)}`
      }

export const parseMatchingConfig = (payload: unknown): ParseResult<MatchingConfig> =>
  toResult(configSchema.safeParse(payload), 'Matching config')

export const parseActiveMatchingConfig = (payload: unknown): ParseResult<ActiveMatchingConfig> =>
  toResult(activeResponseSchema.safeParse(payload), 'Active matching config')

export const parseMatchingConfigDefaults = (
  payload: unknown
): ParseResult<MatchingConfigDefaults> =>
  toResult(defaultsResponseSchema.safeParse(payload), 'Matching config defaults')

// ---------------------------------------------------------------------------
// Payload builders
// ---------------------------------------------------------------------------

/**
 * Weights in backend field names. Values are sent exactly as entered — no
 * rounding and no rescaling — so the server's 100% and 2-decimal-place rules
 * judge what the admin actually typed.
 */
const toConfigFields = (weights: Partial<MatchingWeights>): Record<string, number> =>
  Object.fromEntries(
    MATCHING_WEIGHT_KEYS.filter((key) => weights[key] !== undefined).map((key) => [
      CONFIG_FIELD[key],
      weights[key] as number
    ])
  )

/** A request body in backend field names. */
export type ConfigRequestBody = Record<string, string | number | boolean>

export const toCreateConfigBody = (payload: CreateMatchingConfigPayload): ConfigRequestBody => ({
  name: payload.name,
  ...toConfigFields(payload.weights),
  ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {})
})

export const toUpdateConfigBody = (payload: UpdateMatchingConfigPayload): ConfigRequestBody => ({
  ...(payload.name !== undefined ? { name: payload.name } : {}),
  ...toConfigFields(payload.weights ?? {}),
  ...(payload.isActive !== undefined ? { is_active: payload.isActive } : {})
})

// ---------------------------------------------------------------------------
// Validation errors
// ---------------------------------------------------------------------------

const WEIGHT_KEY_BY_FIELD = Object.fromEntries(
  MATCHING_WEIGHT_KEYS.map((key) => [CONFIG_FIELD[key], key])
) as Record<string, MatchingWeightKey>

/**
 * Validation messages from a failed create/update, keyed for the form.
 * Returns null for anything that is not an API error carrying field errors
 * (network failures, 403, 500), so callers fall back to `error.message`.
 */
export const matchingConfigFieldErrors = (error: unknown): MatchingConfigFieldErrors | null => {
  if (!(error instanceof ApiError) || !error.fields) return null

  const result: MatchingConfigFieldErrors = { weights: {}, other: [] }
  for (const [field, messages] of Object.entries(error.fields)) {
    const message = messages.join(' ')
    if (field === 'weight_total') result.weightTotal = message
    else if (field === 'name') result.name = message
    else if (WEIGHT_KEY_BY_FIELD[field]) result.weights[WEIGHT_KEY_BY_FIELD[field]] = message
    else result.other.push(message)
  }
  return result
}
