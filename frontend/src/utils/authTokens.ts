export const AUTH_ACCESS_TOKEN_KEY = 'auth.accessToken'
export const AUTH_REFRESH_TOKEN_KEY = 'auth.refreshToken'

function writeLocalStorage(key: string, value: string | null | undefined) {
  try {
    if (value) {
      window.localStorage.setItem(key, value)
    } else {
      window.localStorage.removeItem(key)
    }
  } catch {}
}

export function clearAuthTokens() {
  writeLocalStorage(AUTH_ACCESS_TOKEN_KEY, null)
  writeLocalStorage(AUTH_REFRESH_TOKEN_KEY, null)
}
