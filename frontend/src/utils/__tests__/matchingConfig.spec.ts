import { describe, expect, it } from 'vitest'
import { ApiError } from '@/utils/apiError'
import {
  MATCHING_PENALTY_CAP_KEYS,
  MATCHING_WEIGHT_KEYS,
  matchingConfigFieldErrors,
  parseActiveMatchingConfig,
  parseMatchingConfig,
  parseMatchingConfigDefaults,
  toCreateConfigBody,
  toUpdateConfigBody
} from '@/utils/matchingConfig'

/**
 * Fixtures copy what apps/matching_runtime actually returns: DRF serialises the
 * DecimalFields as strings, while `active/`'s `weights` and both `defaults`
 * blocks are plain floats under different key names.
 */
const configRow = {
  id: 3,
  year_weight: '30.00',
  year_max_weight: '20.00',
  timezone_weight: '15.00',
  timezone_max_weight: '25.00',
  size_bonus_weight: '30.00',
  total_weight: '90.00',
  max_total_penalty: '45.00',
  updated_by: 1,
  created_at: '2026-10-06T10:00:00Z',
  updated_at: '2026-10-06T10:05:00Z'
}

const defaultsBlock = {
  baseScore: 100,
  maxTotalPenalty: 100,
  defaults: {
    year_weight: 8.0,
    year_max_weight: 24.0,
    timezone_weight: 2.0,
    timezone_max_weight: 18.0,
    size_bonus_weight: 6.0
  }
}

const expectedDefaults = {
  baseScore: 100,
  maxTotalPenalty: 100,
  weights: {
    yearWeight: 8,
    yearMaxWeight: 24,
    timezoneWeight: 2,
    timezoneMaxWeight: 18,
    sizeBonusWeight: 6
  }
}

const expectOk = <T>(result: { ok: true; data: T } | { ok: false; message: string }): T => {
  if (!result.ok) throw new Error(`expected a successful parse, got: ${result.message}`)
  return result.data
}

describe('weight keys', () => {
  it('has exactly the five scoring weights, in display order', () => {
    // Country only breaks ties (MA4), so it is not one of the weights.
    expect(MATCHING_WEIGHT_KEYS).toEqual([
      'yearWeight',
      'yearMaxWeight',
      'timezoneWeight',
      'timezoneMaxWeight',
      'sizeBonusWeight'
    ])
  })

  it('counts only the caps towards the penalty ceiling', () => {
    // The per-unit weights are bounded by the caps, so the ceiling is stated
    // over the caps alone.
    expect(MATCHING_PENALTY_CAP_KEYS).toEqual(['yearMaxWeight', 'timezoneMaxWeight'])
  })
})

describe('parseMatchingConfig', () => {
  it('turns decimal strings into numbers and snake_case into the frontend shape', () => {
    expect(expectOk(parseMatchingConfig(configRow))).toEqual({
      id: 3,
      weights: {
        yearWeight: 30,
        yearMaxWeight: 20,
        timezoneWeight: 15,
        timezoneMaxWeight: 25,
        sizeBonusWeight: 30
      },
      totalWeight: 90,
      maxTotalPenalty: 45,
      updatedBy: 1,
      createdAt: '2026-10-06T10:00:00Z',
      updatedAt: '2026-10-06T10:05:00Z'
    })
  })

  it('keeps fractional decimals exactly', () => {
    const parsed = expectOk(
      parseMatchingConfig({ ...configRow, year_weight: '33.33', total_weight: '93.33' })
    )
    expect(parsed.weights.yearWeight).toBe(33.33)
    expect(parsed.totalWeight).toBe(93.33)
  })

  it('accepts weights that are already numbers', () => {
    const parsed = expectOk(parseMatchingConfig({ ...configRow, year_weight: 30 }))
    expect(parsed.weights.yearWeight).toBe(30)
  })

  it.each([
    ['an empty string', ''],
    ['a non-numeric string', 'abc'],
    ['null', null]
  ])('rejects %s as a weight instead of reading it as 0', (_label, value) => {
    const result = parseMatchingConfig({ ...configRow, timezone_weight: value })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.message).toContain('timezone_weight')
  })

  it('rejects a config missing a weight', () => {
    const withoutSizeBonus: Record<string, unknown> = { ...configRow }
    delete withoutSizeBonus.size_bonus_weight
    const result = parseMatchingConfig(withoutSizeBonus)
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.message).toContain('size_bonus_weight')
  })

  it('treats a missing editor as null', () => {
    const withoutEditor: Record<string, unknown> = { ...configRow }
    delete withoutEditor.updated_by
    expect(expectOk(parseMatchingConfig(withoutEditor)).updatedBy).toBeNull()
  })
})

describe('parseActiveMatchingConfig', () => {
  it('normalises the active config, its applied weights and the defaults', () => {
    const parsed = expectOk(
      parseActiveMatchingConfig({
        data: configRow,
        // ScoringWeights.as_dict() names one weight differently.
        weights: {
          yearWeight: 30.0,
          yearMaxPenalty: 20.0,
          timezoneWeight: 15.0,
          timezoneMaxPenalty: 25.0,
          sizeBonusWeight: 30.0
        },
        ...defaultsBlock
      })
    )

    expect(parsed.usingBuiltInWeights).toBe(false)
    expect(parsed.config?.id).toBe(3)
    expect(parsed.config?.weights.yearWeight).toBe(30)
    expect(parsed.appliedWeights).toEqual({
      yearWeight: 30,
      yearMaxWeight: 20,
      timezoneWeight: 15,
      timezoneMaxWeight: 25,
      sizeBonusWeight: 30
    })
    expect(parsed.defaults).toEqual(expectedDefaults)
  })

  it('falls back to the built-in weights when no config is saved', () => {
    const parsed = expectOk(
      parseActiveMatchingConfig({
        data: null,
        weights: {
          yearWeight: 8.0,
          yearMaxPenalty: 24.0,
          timezoneWeight: 2.0,
          timezoneMaxPenalty: 18.0,
          sizeBonusWeight: 6.0
        },
        ...defaultsBlock
      })
    )

    expect(parsed.config).toBeNull()
    expect(parsed.usingBuiltInWeights).toBe(true)
    // Points, reported exactly as they are: the total is nobody's business.
    expect(parsed.appliedWeights).toEqual({
      yearWeight: 8,
      yearMaxWeight: 24,
      timezoneWeight: 2,
      timezoneMaxWeight: 18,
      sizeBonusWeight: 6
    })
    expect(parsed.defaults).toEqual(expectedDefaults)
  })

  it('rejects a response without the applied weights', () => {
    const result = parseActiveMatchingConfig({ data: null, ...defaultsBlock })
    expect(result.ok).toBe(false)
  })
})

describe('parseMatchingConfigDefaults', () => {
  it('unwraps the data envelope into the same shape active/ gives', () => {
    expect(expectOk(parseMatchingConfigDefaults({ data: defaultsBlock }))).toEqual(
      expectedDefaults
    )
  })

  it('rejects the unwrapped block, so a shape change is caught', () => {
    expect(parseMatchingConfigDefaults(defaultsBlock).ok).toBe(false)
  })
})

describe('config request bodies', () => {
  const weights = {
    yearWeight: 30,
    yearMaxWeight: 20,
    timezoneWeight: 15,
    timezoneMaxWeight: 25,
    sizeBonusWeight: 30
  }

  it('builds a create body in backend field names', () => {
    expect(toCreateConfigBody({ weights })).toEqual({
      year_weight: 30,
      year_max_weight: 20,
      timezone_weight: 15,
      timezone_max_weight: 25,
      size_bonus_weight: 30
    })
  })

  it('only sends weights, since a config is a singleton server-side', () => {
    expect(toCreateConfigBody({ weights })).not.toHaveProperty('is_active')
  })

  it('sends weights exactly as entered, without rounding', () => {
    const body = toCreateConfigBody({
      weights: { ...weights, yearWeight: 20, timezoneWeight: 15.555 }
    })
    // The total is no rule at all now; the third decimal place is the server's
    // to reject.
    expect(body.year_weight).toBe(20)
    expect(body.timezone_weight).toBe(15.555)
  })

  it('never sends a country weight, even if one is passed in', () => {
    const stale = { ...weights, countryMismatchWeight: 15 } as typeof weights
    expect(toCreateConfigBody({ weights: stale })).not.toHaveProperty(
      'country_mismatch_weight'
    )
    expect(toUpdateConfigBody({ weights: stale })).not.toHaveProperty('country_mismatch_weight')
  })

  it('builds a partial update body with only the fields given', () => {
    expect(
      toUpdateConfigBody({ weights: { yearWeight: 40, timezoneWeight: 10 } })
    ).toEqual({ year_weight: 40, timezone_weight: 10 })
  })
})

describe('matchingConfigFieldErrors', () => {
  const validationError = (fields: Record<string, string[]>) =>
    new ApiError(
      { error: Object.values(fields)[0][0], code: 'invalid', request_id: 'req-1', fields },
      400
    )

  it('exposes the penalty ceiling and per-weight messages under frontend keys', () => {
    const ceilingMessage =
      'Please lower a cap by at least 10.00: at 110 points against a ' +
      '100-point score, the worst pairing would fall below 0.'
    expect(
      matchingConfigFieldErrors(
        validationError({
          penalty_ceiling: [ceilingMessage],
          year_weight: ['Ensure this value is less than or equal to 100.'],
          non_field_errors: ['Something else.']
        })
      )
    ).toEqual({
      penaltyCeiling: ceilingMessage,
      weights: { yearWeight: 'Ensure this value is less than or equal to 100.' },
      other: ['Something else.']
    })
  })

  it('returns null when there is nothing field-specific to show', () => {
    expect(matchingConfigFieldErrors(new Error('Network down'))).toBeNull()
    expect(
      matchingConfigFieldErrors(
        new ApiError({ error: 'Forbidden', code: 'permission_denied', request_id: 'r' }, 403)
      )
    ).toBeNull()
  })
})
