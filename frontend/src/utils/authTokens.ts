export const AUTH_ACCESS_TOKEN_KEY = 'auth.accessToken'
export const AUTH_REFRESH_TOKEN_KEY = 'auth.refreshToken'

interface AuthTokens {
  access?: string | null
  refresh?: string | null
}

function readLocalStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeLocalStorage(key: string, value: string | null | undefined) {
  try {
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {}
}

export function getAccessToken(): string | null {
  return readLocalStorage(AUTH_ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return readLocalStorage(AUTH_REFRESH_TOKEN_KEY)
}

export function saveAuthTokens(tokens: AuthTokens) {
  if ('access' in tokens) {
    writeLocalStorage(AUTH_ACCESS_TOKEN_KEY, tokens.access)
  }

  if ('refresh' in tokens) {
    writeLocalStorage(AUTH_REFRESH_TOKEN_KEY, tokens.refresh)
  }
}

export function clearAuthTokens() {
  writeLocalStorage(AUTH_ACCESS_TOKEN_KEY, null)
  writeLocalStorage(AUTH_REFRESH_TOKEN_KEY, null)
}
