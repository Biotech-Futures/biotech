import { describe, expect, it } from 'vitest'
import { ApiError } from '@/utils/apiError'
import {
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
  name: 'Student v2',
  is_active: true,
  year_weight: '30.00',
  timezone_weight: '15.00',
  timezone_max_weight: '25.00',
  size_bonus_weight: '30.00',
  total_weight: '100.00',
  updated_by: 1,
  created_at: '2026-10-06T10:00:00Z',
  updated_at: '2026-10-06T10:05:00Z'
}

const defaultsBlock = {
  requiredTotal: '100.00',
  defaults: {
    year_weight: 20.0,
    timezone_weight: 30.0,
    timezone_max_weight: 25.0,
    size_bonus_weight: 25.0
  }
}

const expectedDefaults = {
  requiredTotal: 100,
  weights: {
    yearWeight: 20,
    timezoneWeight: 30,
    timezoneMaxWeight: 25,
    sizeBonusWeight: 25
  }
}

const expectOk = <T>(result: { ok: true; data: T } | { ok: false; message: string }): T => {
  if (!result.ok) throw new Error(`expected a successful parse, got: ${result.message}`)
  return result.data
}

describe('parseMatchingConfig', () => {
  it('turns decimal strings into numbers and snake_case into the frontend shape', () => {
    expect(expectOk(parseMatchingConfig(configRow))).toEqual({
      id: 3,
      name: 'Student v2',
      isActive: true,
      weights: {
        yearWeight: 30,
        timezoneWeight: 15,
        timezoneMaxWeight: 25,
        sizeBonusWeight: 30
      },
      totalWeight: 100,
      updatedBy: 1,
      createdAt: '2026-10-06T10:00:00Z',
      updatedAt: '2026-10-06T10:05:00Z'
    })
  })

  it('keeps fractional decimals exactly', () => {
    const parsed = expectOk(
      parseMatchingConfig({ ...configRow, year_weight: '33.33', total_weight: '99.99' })
    )
    expect(parsed.weights.yearWeight).toBe(33.33)
    expect(parsed.totalWeight).toBe(99.99)
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
          timezoneWeight: 2.0,
          timezoneMaxPenalty: 18.0,
          sizeBonusWeight: 6.0
        },
        ...defaultsBlock
      })
    )

    expect(parsed.config).toBeNull()
    expect(parsed.usingBuiltInWeights).toBe(true)
    // The legacy values total 34, not 100, and are reported as they are rather
    // than rescaled into a split they never were.
    expect(parsed.appliedWeights).toEqual({
      yearWeight: 8,
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
    timezoneWeight: 15,
    timezoneMaxWeight: 25,
    sizeBonusWeight: 30
  }

  it('builds a create body in backend field names', () => {
    expect(toCreateConfigBody({ name: 'Student v2', weights })).toEqual({
      name: 'Student v2',
      year_weight: 30,
      timezone_weight: 15,
      timezone_max_weight: 25,
      size_bonus_weight: 30
    })
  })

  it('only sends is_active when it is given', () => {
    expect(toCreateConfigBody({ name: 'Draft', weights, isActive: false })).toMatchObject({
      is_active: false
    })
    expect(toCreateConfigBody({ name: 'Draft', weights })).not.toHaveProperty('is_active')
  })

  it('sends weights exactly as entered, without rescaling to 100', () => {
    const body = toCreateConfigBody({
      name: 'Off by ten',
      weights: { ...weights, yearWeight: 20, timezoneWeight: 15.555 }
    })
    // Totals 90 and has three decimal places: both are the server's to reject.
    expect(body.year_weight).toBe(20)
    expect(body.timezone_weight).toBe(15.555)
  })

  it('builds a partial update body with only the fields given', () => {
    expect(
      toUpdateConfigBody({ weights: { yearWeight: 40, timezoneWeight: 10 } })
    ).toEqual({ year_weight: 40, timezone_weight: 10 })
    expect(toUpdateConfigBody({ name: 'Renamed', isActive: true })).toEqual({
      name: 'Renamed',
      is_active: true
    })
  })
})

describe('matchingConfigFieldErrors', () => {
  const validationError = (fields: Record<string, string[]>) =>
    new ApiError(
      { error: Object.values(fields)[0][0], code: 'invalid', request_id: 'req-1', fields },
      400
    )

  it('exposes the weight total, name and per-weight messages under frontend keys', () => {
    const totalMessage =
      'Matching weights must total exactly 100.00% (currently 90.00%, 10.00% under).'
    expect(
      matchingConfigFieldErrors(
        validationError({
          weight_total: [totalMessage],
          name: ['matching config with this name already exists.'],
          year_weight: ['Ensure this value is less than or equal to 100.'],
          non_field_errors: ['Something else.']
        })
      )
    ).toEqual({
      weightTotal: totalMessage,
      name: 'matching config with this name already exists.',
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
