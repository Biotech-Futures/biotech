import type {
  RegistrationGateway,
  RegistrationGatewayResult,
  RegistrationReceipt,
  RegistrationRequest,
  RegistrationWarning,
} from '@/registration/registrationGateway'
import type { RegistrationIntakeJourney } from '@/registration/registration'
import { apiErrorFromResponse } from '@/utils/apiError'
import { buildSessionHeaders, ensureCsrfCookie } from '@/utils/csrf'
import {
  buildProductionRegistrationRequest,
  registrationFormPath,
  studentRequestPrefixes,
} from './productionRegistration'

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

const normalizeReceipt = (
  data: unknown,
  request: RegistrationRequest,
): RegistrationReceipt | null => {
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
    journey !== request.journey ||
    typeof studentCount !== 'number' ||
    !Number.isInteger(studentCount) ||
    studentCount !== studentRequestPrefixes(request).length ||
    typeof submittedAt !== 'string' ||
    !submittedAt.trim() ||
    Number.isNaN(Date.parse(submittedAt))
  ) {
    return null
  }

  const groupCode = source.group_code ?? source.groupCode
  return {
    referenceCode,
    journey: journey as RegistrationIntakeJourney,
    studentCount,
    submittedAt,
    ...(typeof groupCode === 'string' && groupCode ? { groupCode } : {}),
  }
}

const normalizeWarnings = (
  data: unknown,
  request: RegistrationRequest,
): RegistrationWarning[] | null => {
  if (!isRecord(data) || data.fields || !Array.isArray(data.warnings) || !data.warnings.length)
    return null
  const warnings: RegistrationWarning[] = []
  const overrideFields = new Set<string>()
  for (const item of data.warnings) {
    if (
      !isRecord(item) ||
      typeof item.code !== 'string' ||
      !item.code ||
      typeof item.field !== 'string' ||
      typeof item.override_field !== 'string' ||
      typeof item.message !== 'string' ||
      !item.message.trim()
    )
      return null
    const match =
      /^students\.(\d+)\.overrides\.(ConfirmSchoolOverride|ConfirmNameEmailOverride)$/.exec(
        item.override_field,
      )
    if (
      !match ||
      overrideFields.has(item.override_field) ||
      !studentRequestPrefixes(request)[Number(match[1])] ||
      item.field !==
        `students.${match[1]}.${match[2] === 'ConfirmSchoolOverride' ? 'school' : 'email'}`
    )
      return null
    overrideFields.add(item.override_field)
    warnings.push({
      code: item.code,
      field: registrationFormPath(request, item.field),
      overrideField: item.override_field,
      message: item.message,
    })
  }
  return warnings
}

export const createHttpRegistrationGateway = ({
  endpoint,
  fetchImpl = fetch,
  ensureCsrf = ensureCsrfCookie,
}: HttpRegistrationGatewayOptions): RegistrationGateway => ({
  async submit(request, options = {}): Promise<RegistrationGatewayResult> {
    const csrfApiBaseUrl = csrfBaseUrl(endpoint)
    let csrfReady = false
    try {
      csrfReady = await ensureCsrf(csrfApiBaseUrl)
    } catch {
      csrfReady = false
    }
    if (!csrfReady) {
      return {
        ok: false,
        message: 'A secure registration session could not be initialized. Refresh and try again.',
      }
    }

    let body: string | FormData
    const headers = buildSessionHeaders({
      includeCSRF: true,
      csrfApiBaseUrl,
      headers: { Accept: 'application/json' },
    })
    try {
      const idempotencyKey = options.idempotencyKey || crypto.randomUUID()
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idempotencyKey)) {
        throw new Error('Registration requires a UUID retry key.')
      }
      headers.set('Idempotency-Key', idempotencyKey)
      if (options.invitationToken) headers.set('X-Registration-Invitation', options.invitationToken)
      const production = buildProductionRegistrationRequest(request, options.overrides)
      // An admin's students' supervisor, when they choose one.
      if (options.supervisorEmail?.trim()) {
        ;(production.payload as Record<string, unknown>).supervisorEmail = options.supervisorEmail.trim()
      }
      body = JSON.stringify(production)
      if (Object.keys(options.attachments || {}).length) {
        const multipart = new FormData()
        multipart.append('request', body)
        for (const [prefix, file] of Object.entries(options.attachments || {})) {
          const index = studentRequestPrefixes(request).indexOf(prefix)
          if (index < 0) throw new Error('Invalid registration photo field.')
          multipart.append(`students.${index}`, file)
        }
        headers.delete('Content-Type')
        body = multipart
      }
    } catch (error) {
      return {
        ok: false,
        message:
          error instanceof Error
            ? error.message
            : 'The registration request could not be prepared.',
      }
    }

    let response: Response
    try {
      response = await fetchImpl(endpoint, {
        method: 'POST',
        credentials: 'include',
        headers,
        body,
      })
    } catch {
      return {
        ok: false,
        message:
          'The registration service could not be reached. Check your connection and try again.',
      }
    }

    if (!response.ok) {
      try {
        const data: unknown = await response
          .clone()
          .json()
          .catch(() => null)
        if (response.status === 400 && isRecord(data) && 'warnings' in data && !data.fields) {
          const warnings = normalizeWarnings(data, request)
          return warnings
            ? {
                ok: false,
                message:
                  typeof data.error === 'string'
                    ? data.error
                    : 'Please check these registration warnings.',
                warnings,
              }
            : {
                ok: false,
                message:
                  'The registration service returned invalid warnings. Contact support before continuing.',
              }
        }
        const error = await apiErrorFromResponse(response, 'Registration could not be submitted.')
        const fieldErrors = error.fields
          ? Object.fromEntries(
              Object.entries(error.fields).map(([field, messages]) => [
                registrationFormPath(request, field),
                messages.join(' '),
              ]),
            )
          : undefined
        return { ok: false, message: error.message, fieldErrors }
      } catch {
        return { ok: false, message: 'Registration could not be submitted. Try again.' }
      }
    }

    if (response.status !== 200 && response.status !== 201) {
      return {
        ok: false,
        message:
          'The registration service did not confirm a saved registration. Contact support before retrying.',
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

    const receipt = normalizeReceipt(data, request)
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
  apiBaseUrl?: string,
): RegistrationGateway => {
  const normalizedEndpoint = endpoint?.trim()
  const base = apiBaseUrl?.trim().replace(/\/+$/, '') || ''
  return createHttpRegistrationGateway({
    endpoint: normalizedEndpoint || `${base}/api/v1/registration`,
  })
}
