/**
 * @file matchingAPI.ts
 * @description Requests for the matching scoring-weight config (MA1).
 *
 * These routes live at `/matching/configs/` on the backend (apps/matching_runtime),
 * not under `/api/v1/admin`, so they cannot go through adminAPI's transport.
 * Same session auth and CSRF handling as the other feature modules.
 *
 * Every function returns the normalised shapes from matchingConfig.ts. A
 * rejected save throws the ApiError from apiErrorFromResponse — pass it to
 * `matchingConfigFieldErrors()` for per-field messages. A response in an
 * unexpected shape throws a plain Error rather than handing the UI defaults.
 */
import { apiErrorFromResponse } from './apiError'
import { buildSessionHeaders, ensureCsrfCookie } from './csrf'
import type { ParseResult } from './adminMatching'
import {
  type ActiveMatchingConfig,
  type CreateMatchingConfigPayload,
  type MatchingConfig,
  type MatchingConfigDefaults,
  type UpdateMatchingConfigPayload,
  parseActiveMatchingConfig,
  parseMatchingConfig,
  parseMatchingConfigDefaults,
  toCreateConfigBody,
  toUpdateConfigBody
} from './matchingConfig'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const CONFIGS_PATH = '/matching/configs'

async function requestJson(path: string, options: RequestInit = {}): Promise<unknown> {
  const method = String(options.method || 'GET').toUpperCase()
  const includeCSRF = !['GET', 'HEAD', 'OPTIONS'].includes(method)

  if (includeCSRF) {
    const csrfReady = await ensureCsrfCookie(API_BASE_URL)
    if (!csrfReady) {
      throw new Error('Could not initialize a secure session. Please refresh and try again.')
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...options,
    headers: buildSessionHeaders({
      includeCSRF,
      headers: { Accept: 'application/json' }
    })
  })

  if (!response.ok) {
    throw await apiErrorFromResponse(response, 'Matching config request failed')
  }

  const text = await response.text()
  return text ? JSON.parse(text) : null
}

const unwrap = <T>(result: ParseResult<T>): T => {
  if (!result.ok) throw new Error(result.message)
  return result.data
}

/** The config in force, or the built-in weights when none is saved. */
export const fetchActiveMatchingConfig = async (): Promise<ActiveMatchingConfig> =>
  unwrap(parseActiveMatchingConfig(await requestJson(`${CONFIGS_PATH}/active/`)))

/** A complete, valid weight split to start a new config from. */
export const fetchMatchingConfigDefaults = async (): Promise<MatchingConfigDefaults> =>
  unwrap(parseMatchingConfigDefaults(await requestJson(`${CONFIGS_PATH}/defaults/`)))

/**
 * Save a config. A config is a singleton, so the new row replaces whatever was
 * stored before.
 */
export const createMatchingConfig = async (
  payload: CreateMatchingConfigPayload
): Promise<MatchingConfig> =>
  unwrap(
    parseMatchingConfig(
      await requestJson(`${CONFIGS_PATH}/`, {
        method: 'POST',
        body: JSON.stringify(toCreateConfigBody(payload))
      })
    )
  )

/** Change an existing config (PATCH — only the fields given are sent). */
export const updateMatchingConfig = async (
  id: number,
  payload: UpdateMatchingConfigPayload
): Promise<MatchingConfig> =>
  unwrap(
    parseMatchingConfig(
      await requestJson(`${CONFIGS_PATH}/${id}/`, {
        method: 'PATCH',
        body: JSON.stringify(toUpdateConfigBody(payload))
      })
    )
  )
