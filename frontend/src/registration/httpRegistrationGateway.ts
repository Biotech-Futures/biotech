import type {
  RegistrationGateway,
  RegistrationGatewayResult,
  RegistrationReceipt,
} from '@/registration/registrationGateway'
import type { RegistrationIntakeJourney } from '@/registration/registration'
import { apiErrorFromResponse } from '@/utils/apiError'
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'

interface HttpRegistrationGatewayOptions {
  endpoint: string
  fetchImpl?: typeof fetch
  ensureCsrf?: typeof ensureCsrfCookie
}

type ReceiptSource = Record<string, unknown>

const isRecord = (value: unknown): value is ReceiptSource =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const intakeJourneys = new Set<RegistrationIntakeJourney>([
  'student_individual',
  'student_team',
  'supervisor_individual',
  'supervisor_group',
  'supervisor_csv',
  'mentor',
])

const csrfBaseUrl = (endpoint: string) => new URL(endpoint, window.location.origin).origin

const normalizeReceipt = (data: unknown): RegistrationReceipt | null => {
  const root = isRecord(data) ? data : null
  const source = root && isRecord(root.data) ? root.data : root
  if (!source) return null

  const referenceCode = source.reference_code ?? source.referenceCode
  const journey = source.journey
  const studentCount = source.student_count ?? source.studentCount
  const submittedAt = source.created_at ?? source.submittedAt

  if (
    typeof referenceCode !== 'string' ||
    !referenceCode.trim() ||
    typeof journey !== 'string' ||
    !intakeJourneys.has(journey as RegistrationIntakeJourney) ||
    typeof studentCount !== 'number' ||
    !Number.isFinite(studentCount) ||
    studentCount < 0 ||
    typeof submittedAt !== 'string' ||
    !submittedAt.trim()
  ) {
    return null
  }

  return {
    referenceCode,
    journey: journey as RegistrationIntakeJourney,
    studentCount,
    submittedAt,
  }
}

/**
 * HTTP contract:
 * - Success: a direct receipt or `{ data: receipt }`, accepting snake_case or camelCase keys.
 * - Error: `{ error, code?, request_id?, fields?: Record<string, string | string[]> }`.
 * Field keys must use the frontend form paths so the page can attach messages to controls.
 */
export const createHttpRegistrationGateway = ({
  endpoint,
  fetchImpl = fetch,
  ensureCsrf = ensureCsrfCookie,
}: HttpRegistrationGatewayOptions): RegistrationGateway => ({
  async submit(request): Promise<RegistrationGatewayResult> {
    let csrfReady = false
    try {
      csrfReady = await ensureCsrf(csrfBaseUrl(endpoint))
    } catch {
      csrfReady = false
    }
    if (!csrfReady) {
      return {
        ok: false,
        message: 'A secure registration session could not be initialized. Refresh and try again.',
      }
    }

    let response: Response
    try {
      response = await fetchImpl(endpoint, {
        method: 'POST',
        credentials: 'include',
        headers: buildSessionHeaders({
          includeCSRF: true,
          headers: { Accept: 'application/json' },
        }),
        body: JSON.stringify(request),
      })
    } catch {
      return {
        ok: false,
        message: 'The registration service could not be reached. Check your connection and try again.',
      }
    }

    if (!response.ok) {
      try {
        const error = await apiErrorFromResponse(response, 'Registration could not be submitted.')
        const fieldErrors = error.fields
          ? Object.fromEntries(
              Object.entries(error.fields).map(([field, messages]) => [field, messages.join(' ')]),
            )
          : undefined
        return { ok: false, message: error.message, fieldErrors }
      } catch {
        return { ok: false, message: 'Registration could not be submitted. Try again.' }
      }
    }

    let data: unknown
    try {
      data = await response.json()
    } catch {
      return {
        ok: false,
        message: 'The registration service returned an unreadable success response. Try again.',
      }
    }

    const receipt = normalizeReceipt(data)
    if (!receipt) {
      return {
        ok: false,
        message: 'The registration service returned an incomplete receipt. Try again.',
      }
    }

    return { ok: true, receipt }
  },
})

export const configuredRegistrationGateway = (
  endpoint: string | undefined,
): RegistrationGateway | null => {
  const normalizedEndpoint = endpoint?.trim()
  return normalizedEndpoint ? createHttpRegistrationGateway({ endpoint: normalizedEndpoint }) : null
}
