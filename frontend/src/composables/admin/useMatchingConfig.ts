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
  MATCHING_WEIGHT_KEYS,
  matchingConfigFieldErrors
} from '@/utils/matchingConfig'

/** Labels and help copy for the five weight inputs, in display order. */
export const MATCHING_WEIGHT_FIELDS: { key: MatchingWeightKey; label: string; help: string }[] = [
  {
    key: 'yearWeight',
    label: 'Year',
    help: 'Taken off the score for each year of year-level difference between students.'
  },
  {
    key: 'countryMismatchWeight',
    label: 'Country',
    help: 'Country is used separately as a tie-breaker when otherwise suitable matches are tied. This configured value is currently reported in the score breakdown and counts towards the required 100% total.'
  },
  {
    key: 'timezoneWeight',
    label: 'Timezone',
    help: 'Taken off the score for each hour of timezone difference between students.'
  },
  {
    key: 'timezoneMaxWeight',
    label: 'Timezone cap',
    help: 'The most the timezone penalty can take off a score, however far apart students are.'
  },
  {
    key: 'sizeBonusWeight',
    label: 'Group size bonus',
    help: 'Added to the score for forming a full-sized group.'
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
 * keep the total exact: 33.33 + 33.33 + 33.34 is 100 here, not
 * 100.00000000000001, and more than two decimal places is rejected rather than
 * rounded, matching the backend's DecimalField(decimal_places=2).
 */
const toHundredths = (value: WeightInput): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  if (value < 0 || value > 100) return null
  const hundredths = Math.round(value * 100)
  return Math.abs(value * 100 - hundredths) < 1e-6 ? hundredths : null
}

const formatPercent = (hundredths: number) =>
  hundredths % 100 === 0 ? String(hundredths / 100) : (hundredths / 100).toFixed(2)

/**
 * State for the student matching weights editor (MA1).
 *
 * Edits the active config only: with one saved, saving PATCHes it; with none,
 * saving POSTs a new config, which the backend makes active. Weights are sent
 * exactly as entered — a total other than `requiredTotal` blocks saving
 * rather than being rebalanced.
 */
export function useMatchingConfig() {
  const status = ref<LoadStatus>('loading')
  const loadError = ref('')
  const active = ref<ActiveMatchingConfig | null>(null)

  const name = ref('')
  const weights = ref<Record<MatchingWeightKey, WeightInput>>({
    yearWeight: '',
    countryMismatchWeight: '',
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
    // With no saved config the built-in weights are not a valid percentage
    // split (they total 46), so the form starts from the suggested defaults.
    const source = state.config?.weights ?? state.defaults.weights
    name.value = state.config?.name ?? ''
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

  const requiredTotal = computed(() => active.value?.defaults.requiredTotal ?? 100)
  const isFirstConfig = computed(() => active.value?.config === null)

  /** Keys whose input is empty, out of range or has too many decimals. */
  const invalidWeightKeys = computed(() =>
    MATCHING_WEIGHT_KEYS.filter((key) => toHundredths(weights.value[key]) === null)
  )

  const totalHundredths = computed(() =>
    MATCHING_WEIGHT_KEYS.reduce((sum, key) => sum + (toHundredths(weights.value[key]) ?? 0), 0)
  )

  const requiredHundredths = computed(() => Math.round(requiredTotal.value * 100))

  const totalLabel = computed(
    () => `${formatPercent(totalHundredths.value)} / ${formatPercent(requiredHundredths.value)}%`
  )

  const totalMatches = computed(
    () =>
      invalidWeightKeys.value.length === 0 &&
      totalHundredths.value === requiredHundredths.value
  )

  const canSave = computed(
    () =>
      status.value === 'ready' &&
      !saving.value &&
      name.value.trim().length > 0 &&
      totalMatches.value
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
        fieldErrors.value = { ...fieldErrors.value, weights: {}, weightTotal: undefined }
      }
    },
    { deep: true, flush: 'sync' }
  )
  watch(
    name,
    () => {
      notice.value = ''
      if (fieldErrors.value) fieldErrors.value = { ...fieldErrors.value, name: undefined }
    },
    { flush: 'sync' }
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
            name: name.value.trim(),
            weights: payloadWeights
          })
        : await createMatchingConfig({
            name: name.value.trim(),
            weights: payloadWeights,
            isActive: true
          })

      // The saved config is now the one in force: a new config is created
      // active, and PATCH keeps the active one active.
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
    name,
    weights,
    saving,
    saveError,
    fieldErrors,
    notice,
    requiredTotal,
    isFirstConfig,
    totalLabel,
    totalMatches,
    canSave,
    weightError,
    load,
    save
  }
}
