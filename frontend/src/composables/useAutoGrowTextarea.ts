import { nextTick, onScopeDispose, watch } from 'vue'
import type { WatchSource } from 'vue'

type MaybeTextarea = HTMLTextAreaElement | null | undefined

/**
 * Chat-composer auto-grow, the way WhatsApp/Slack/Discord behave: start at one
 * row, track the draft's height up to the element's CSS max-height, then hand
 * scrolling back to the textarea. Height collapses again as lines are deleted.
 *
 * Watches `source` (the v-model ref) rather than @input so programmatic writes
 * — clearing the draft on send, mention insertion, edit prefill — resize too.
 * `resize()` is returned for the one case a watcher can't see: re-showing a
 * textarea whose text didn't change (e.g. re-opening the same message edit).
 */
export function useAutoGrowTextarea(
  getEl: () => MaybeTextarea,
  source: WatchSource<unknown>,
  onResize?: () => void,
) {
  const resize = () => {
    const el = getEl()
    if (!el) return
    // Collapse first so removing lines shrinks the box instead of latching
    // at its tallest-ever height.
    el.style.height = 'auto'
    // Global border-box sizing: scrollHeight excludes borders, so add them
    // back or the box lands a couple px short and shows a scrollbar.
    const styles = window.getComputedStyle(el)
    const borders =
      parseFloat(styles.borderTopWidth) + parseFloat(styles.borderBottomWidth)
    el.style.height = `${el.scrollHeight + borders}px`
  }

  watch(source, () => {
    void nextTick(() => {
      resize()
      onResize?.()
    })
  })

  // Width changes (device rotation, window resize, layout breakpoints) re-wrap
  // the draft, which would leave a stale pixel height until the next keystroke.
  window.addEventListener('resize', resize)
  onScopeDispose(() => window.removeEventListener('resize', resize))

  return { resize }
}
