
export function getInitials(text: string): string {
  if (!text) return 'GR'

  const words = String(text).trim().split(/\s+/).slice(0, 2)

  // ['Shiqi', 'Fang'].map(word => word[0])    ['S', 'F']
  return words.map(word => word[0]?.toUpperCase() || '').join('') || 'GR'
}

// login_emial-1
/*
  maskedEmail generates the obfuscated email shown on the OTP screen.
  It is only for safe display and does not modify the actual email value sent to the backend.
  The rules are:
  1. If parsing fails, return the raw value
  2. If the name part is very short, keep only the first character
  3. If the name part is longer, keep the first two characters and mask the rest
*/
export function maskEmail(email: string): string {
  const value = String(email || '').trim()
  const parts = value.split('@')

  if (parts.length !== 2) {
    return value
  }

  const [name, domain] = parts

  if (name.length <= 2) {
    return `${name[0] || '*'}***@${domain}`
  }

  return `${name.slice(0, 2)}***@${domain}`
}

// login_emial-2
export function isValidEmail(email: string): boolean {
  const value = String(email || '').trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}
