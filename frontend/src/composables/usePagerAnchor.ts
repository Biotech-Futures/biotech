/**
 * Paging keeps a table's bottom bar where it is on screen, so its < and >
 * stay under the mouse whatever the rows' heights: the page scrolls by as
 * much as the bar moved, down for a taller page and up for a shorter one, so
 * what's above the table moves rather than the bar. Only when a shorter page
 * can't scroll up that far (too near the top) does the table keep room below
 * its rows, just what the scrolling fell short by.
 *
 * ``turn(go)`` pages (``go`` changes the page); ``settle()`` runs once the
 * new rows are drawn; ``reset()`` lets any held room go, for a new search,
 * sort or rows per page.
 */
import type { Ref } from 'vue'

/** What scrolls ``el`` into view: its nearest scrolling ancestor, else the window. */
const scrollerOf = (el: HTMLElement): Element | Window => {
  for (let node = el.parentElement; node; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node)
    if ((overflowY === 'auto' || overflowY === 'scroll') && node.scrollHeight > node.clientHeight) return node
  }
  return window
}

/** How far ``scroller`` is scrolled down: as far as it can scroll back up. */
const scrolledDown = (scroller: Element | Window) =>
  scroller === window ? window.scrollY : (scroller as Element).scrollTop

export function usePagerAnchor(bar: Ref<HTMLElement | null>, box: Ref<HTMLElement | null>) {
  // Where the bar was on screen when the page was turned; null once settled.
  let barTop: number | null = null

  /** Room kept for the table box, at least ``px`` tall; none for null. */
  const hold = (px: number | null) => {
    if (box.value) box.value.style.minHeight = px ? `${px}px` : ''
  }

  const turn = (go: () => void) => {
    barTop = bar.value ? bar.value.getBoundingClientRect().top : null
    go()
  }

  const settle = () => {
    if (barTop === null || !bar.value) return
    const was = barTop
    barTop = null
    // The new rows at their own height, without room held for the last page.
    hold(null)
    const moved = bar.value.getBoundingClientRect().top - was
    if (!moved) return
    const scroller = scrollerOf(bar.value)
    // Back up by as much as it rose, but no further than the top...
    const by = Math.max(moved, -scrolledDown(scroller))
    if (by) scroller.scrollBy(0, by)
    // ...with room below the rows for what that fell short by.
    if (by > moved && box.value) hold(box.value.offsetHeight + by - moved)
  }

  const reset = () => {
    barTop = null
    hold(null)
  }

  return { turn, settle, reset }
}
