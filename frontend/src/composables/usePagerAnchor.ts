/**
 * Paging keeps a table's bottom bar where it is on screen, so its < and >
 * stay under the mouse whatever the rows' heights: while paging, the table
 * keeps at least the height it had (a shorter page leaves room below its
 * rows rather than pulling the bar up), and when a page is taller, the page
 * scrolls by as much as the bar moved down.
 *
 * ``turn(go)`` pages (``go`` changes the page); ``settle()`` runs once the
 * new rows are drawn; ``reset()`` lets the height go again, for a new search,
 * sort or rows per page; ``boxStyle`` is the table box's held height.
 */
import { computed, ref, type Ref } from 'vue'

/** What scrolls ``el`` into view: its nearest scrolling ancestor, else the window. */
const scrollerOf = (el: HTMLElement): Element | Window => {
  for (let node = el.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if ((overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight) return node
  }
  return window
}

export function usePagerAnchor(bar: Ref<HTMLElement | null>, box: Ref<HTMLElement | null>) {
  const minHeight = ref<number | null>(null)
  // Where the bar was on screen when the page was turned; null once settled.
  let barTop: number | null = null

  const turn = (go: () => void) => {
    if (box.value) minHeight.value = Math.max(minHeight.value ?? 0, box.value.offsetHeight)
    barTop = bar.value ? bar.value.getBoundingClientRect().top : null
    go()
  }

  const settle = () => {
    if (barTop === null || !bar.value) return
    const moved = bar.value.getBoundingClientRect().top - barTop
    barTop = null
    if (moved) scrollerOf(bar.value).scrollBy(0, moved)
  }

  const reset = () => {
    minHeight.value = null
    barTop = null
  }

  const boxStyle = computed(() => (minHeight.value ? { minHeight: `${minHeight.value}px` } : undefined))

  return { turn, settle, reset, boxStyle }
}
