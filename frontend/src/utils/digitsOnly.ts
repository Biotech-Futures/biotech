// A number box (with its up and down arrows) that takes whole numbers alone:
// a number box lets "e", "+", "-" and "." in, so their keys and any paste
// with them are refused.

export const refuseNonDigitKey = (event: KeyboardEvent) => {
  if (event.key.length === 1 && !/\d/.test(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey) {
    event.preventDefault()
  }
}

export const refuseNonDigitPaste = (event: ClipboardEvent) => {
  if (/\D/.test(event.clipboardData?.getData('text') ?? '')) event.preventDefault()
}

/** The box's digits, cut to `maxLength`, written back to it when cut. */
export const keptDigits = (field: HTMLInputElement, maxLength?: number) => {
  const digits = field.value.replace(/\D/g, '')
  const kept = maxLength ? digits.slice(0, maxLength) : digits
  if (kept !== field.value) field.value = kept
  return kept
}
