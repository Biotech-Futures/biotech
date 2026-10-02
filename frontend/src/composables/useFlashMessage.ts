import { onBeforeUnmount, ref } from 'vue'

/** How long a success message stays on screen before clearing itself. */
export const FLASH_MESSAGE_MS = 3500

/**
 * A success message that clears itself after FLASH_MESSAGE_MS. `show()`
 * restarts the countdown, so back to back successes each get the full time.
 * Writing `message` directly (e.g. resetting it to '') still works; the
 * pending timer is harmless and is cleaned up on unmount.
 */
export function useFlashMessage(ms = FLASH_MESSAGE_MS) {
  const message = ref('')
  let timer: ReturnType<typeof setTimeout> | null = null

  const stop = () => {
    if (timer != null) {
      clearTimeout(timer)
      timer = null
    }
  }

  // ``forMs``: longer for a message with more to read.
  const show = (text: string, forMs = ms) => {
    stop()
    message.value = text
    timer = setTimeout(() => {
      timer = null
      message.value = ''
    }, forMs)
  }

  onBeforeUnmount(stop)

  return { message, show }
}
