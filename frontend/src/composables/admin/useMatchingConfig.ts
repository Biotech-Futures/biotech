import { computed, ref, watch } from 'vue'
import { ApiError, logApiError } from '@/utils/apiError'
import {
  createMatchingConfig,
  fetchActiveMatchingConfig,
  updateMatchingConfig
} from '@/utils/matchingAPI'
import {
  type ActiveMatchingConfig,
  type MatchingConfigFieldErrors,
  type MatchingWeightKey,
  type MatchingWeights,
  MATCHING_PENALTY_CAP_KEYS,
  MATCHING_WEIGHT_KEYS,
  matchingConfigFieldErrors
} from '@/utils/matchingConfig'

/** Labels and help copy for the five weight inputs, in display order. */
export const MATCHING_WEIGHT_FIELDS: { key: MatchingWeightKey; label: string; help: string }[] = [
  {
    key: 'yearWeight',
    label: 'Year',
    help: 'Points taken off the score for each year of year-level difference between students.'
  },
  {
    key: 'yearMaxWeight',
    label: 'Year cap',
    help: 'The most the year penalty can take off a score, however far apart students are.'
  },
  {
    key: 'timezoneWeight',
    label: 'Timezone',
    help: 'Points taken off the score for each hour of timezone difference between students.'
  },
  {
    key: 'timezoneMaxWeight',
    label: 'Timezone cap',
    help: 'The most the timezone penalty can take off a score, however far apart students are.'
  },
  {
    key: 'sizeBonusWeight',
    label: 'Group size bonus',
    help: 'Points added to the score for forming a full-sized group.'
  }
]

export const FORBIDDEN_MESSAGE =
  'You do not have permission to change the matching weights. Ask a staff administrator.'

/** A weight input's value: a number, or '' while the field is empty. */
type WeightInput = number | string

type LoadStatus = 'loading' | 'ready' | 'error' | 'forbidden'

const isForbidden = (error: unknown) => error instanceof ApiError && error.status === 403

const errorMessage = (error: unknown, fallback: string) =>
  error instanceof Error && error.message ? error.message : fallback

/**
 * The value in hundredths, or null when it is not a usable weight. Hundredths
 * keep sums exact: 33.33 + 33.34 is 66.67 here, not 66.67000000000001, and more
 * than two decimal places is rejected rather than rounded, matching the
 * backend's DecimalField(decimal_places=2).
 */
const toHundredths = (value: WeightInput): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  if (value < 0 || value > 100) return null
  const hundredths = Math.round(value * 100)
  return Math.abs(value * 100 - hundredths) < 1e-6 ? hundredths : null
}

/** Hundredths as a plain point figure: 4200 -> '42', 4250 -> '42.50'. */
const formatPoints = (hundredths: number) =>
  hundredths % 100 === 0 ? String(hundredths / 100) : (hundredths / 100).toFixed(2)

/**
 * State for the student matching weights editor (MA1).
 *
 * Edits the active config only: with one saved, saving PATCHes it; with none,
 * saving POSTs a new config, which the backend makes active. Weights are raw
 * points sent exactly as entered: they may total anything, and nothing is
 * rebalanced. What blocks saving is penalty caps adding up to more than the
 * base score, which would flatten every worst-case pairing to 0.
 */
export function useMatchingConfig() {
  const status = ref<LoadStatus>('loading')
  const loadError = ref('')
  const active = ref<ActiveMatchingConfig | null>(null)

  const weights = ref<Record<MatchingWeightKey, WeightInput>>({
    yearWeight: '',
    yearMaxWeight: '',
    timezoneWeight: '',
    timezoneMaxWeight: '',
    sizeBonusWeight: ''
  })

  const saving = ref(false)
  /** A save failure not tied to one field (network, 403, non-field errors). */
  const saveError = ref('')
  const fieldErrors = ref<MatchingConfigFieldErrors | null>(null)
  const notice = ref('')

  const fillForm = (state: ActiveMatchingConfig) => {
    // With no saved config the built-in weights apply, and they are also what
    // the defaults block suggests, so either source starts the form correctly.
    const source = state.config?.weights ?? state.defaults.weights
    weights.value = { ...source }
  }

  const load = async () => {
    status.value = 'loading'
    loadError.value = ''
    try {
      const state = await fetchActiveMatchingConfig()
      active.value = state
      fillForm(state)
      status.value = 'ready'
    } catch (error) {
      logApiError('admin.matching.config.load', error)
      if (isForbidden(error)) {
        status.value = 'forbidden'
        return
      }
      loadError.value = errorMessage(error, 'Unable to load the matching weights.')
      status.value = 'error'
    }
  }

  // -- Derived ----------------------------------------------------------------

  const baseScore = computed(() => active.value?.defaults.baseScore ?? 100)

  /** The ceiling the caps are held to, as the backend reports it. */
  const maxTotalPenalty = computed(() => active.value?.defaults.maxTotalPenalty ?? 100)

  /** Keys whose input is empty, out of range or has too many decimals. */
  const invalidWeightKeys = computed(() =>
    MATCHING_WEIGHT_KEYS.filter((key) => toHundredths(weights.value[key]) === null)
  )

  /** What the two caps together would take off a score, in hundredths. */
  const penaltyHundredths = computed(() =>
    MATCHING_PENALTY_CAP_KEYS.reduce((sum, key) => sum + (toHundredths(weights.value[key]) ?? 0), 0)
  )

  const ceilingHundredths = computed(() => Math.round(maxTotalPenalty.value * 100))

  /** True once the caps could wipe out more than the whole base score. */
  const ceilingExceeded = computed(
    () =>
      invalidWeightKeys.value.length === 0 &&
      penaltyHundredths.value > ceilingHundredths.value
  )

  /** The score of the worst pairing these weights allow, floored at 0. */
  const worstCaseLabel = computed(() => {
    const remaining = Math.round(baseScore.value * 100) - penaltyHundredths.value
    return formatPoints(Math.max(0, remaining))
  })

  /** Just the caps' total: "42". */
  const penaltyTotalLabel = computed(() => formatPoints(penaltyHundredths.value))

  /** "42 of 100 points" — what the configured caps can actually take off. */
  const penaltyLabel = computed(
    () => `${penaltyTotalLabel.value} of ${formatPoints(ceilingHundredths.value)}`
  )

  /** How far over the ceiling the caps are, for a message that says what to do. */
  const overshootLabel = computed(() =>
    formatPoints(Math.max(0, penaltyHundredths.value - ceilingHundredths.value))
  )

  const canSave = computed(
    () =>
      status.value === 'ready' &&
      !saving.value &&
      invalidWeightKeys.value.length === 0 &&
      !ceilingExceeded.value
  )

  /** Server message for a field, else a local one once the input is unusable. */
  const weightError = (key: MatchingWeightKey): string => {
    const serverError = fieldErrors.value?.weights[key]
    if (serverError) return serverError
    if (invalidWeightKeys.value.includes(key)) {
      return 'Enter a number from 0 to 100, with at most 2 decimal places.'
    }
    return ''
  }

  // A server message describes the value that was sent; once the admin edits
  // that field it no longer applies. Also drops a stale "Saved" notice.
  // `sync` so a refill inside save() is handled before its own notice is set.
  watch(
    weights,
    () => {
      notice.value = ''
      if (fieldErrors.value) {
        fieldErrors.value = { ...fieldErrors.value, weights: {}, penaltyCeiling: undefined }
      }
    },
    { deep: true, flush: 'sync' }
  )

  // -- Actions ----------------------------------------------------------------

  const save = async (): Promise<boolean> => {
    if (!canSave.value || !active.value) return false

    saving.value = true
    saveError.value = ''
    fieldErrors.value = null
    notice.value = ''

    // Exactly what the admin typed: no rounding and no rebalancing.
    const payloadWeights = { ...weights.value } as MatchingWeights
    const existing = active.value.config

    try {
      const saved = existing
        ? await updateMatchingConfig(existing.id, {
            weights: payloadWeights
          })
        : await createMatchingConfig({
            weights: payloadWeights
          })

      // The saved config is the one in force: saving a row replaces whatever
      // was stored before.
      active.value = {
        ...active.value,
        config: saved,
        appliedWeights: saved.weights,
        usingBuiltInWeights: false
      }
      fillForm(active.value)
      notice.value = 'Saved. The next student matching run will use these weights.'
      return true
    } catch (error) {
      logApiError('admin.matching.config.save', error)
      if (isForbidden(error)) {
        saveError.value = FORBIDDEN_MESSAGE
        return false
      }
      const fields = matchingConfigFieldErrors(error)
      fieldErrors.value = fields
      // Field messages render beside their inputs; anything else is general.
      saveError.value = fields
        ? fields.other.join(' ')
        : errorMessage(error, 'Unable to save the matching weights.')
      return false
    } finally {
      saving.value = false
    }
  }

  return {
    status,
    loadError,
    active,
    weights,
    saving,
    saveError,
    fieldErrors,
    notice,
    baseScore,
    maxTotalPenalty,
    penaltyLabel,
    overshootLabel,
    worstCaseLabel,
    ceilingExceeded,
    canSave,
    weightError,
    load,
    save
  }
}
