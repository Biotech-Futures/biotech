import { onScopeDispose, ref, watch } from 'vue'

/**
 * A second sideways scrollbar for a wide table, laid just under its heading
 * row and moving with the one at the bottom, so the table scrolls sideways
 * without going down to the end of it first. Only for a table too wide for
 * its box and taller than the window: one that fits on screen already shows
 * its bottom scrollbar.
 *
 * Bind `wrapEl` to the scrolling box (`.table-scroll-box`, with
 * `@scroll="syncFromTable"`),
 * `headEl` to the table's <thead>, and `topScrollEl` to the bar
 * (`.table-top-scroll`, with `@scroll="syncFromTop"`) inside a
 * `.table-scroll-frame` around the box. A `.table-scroll-gap` row at the top
 * of the <tbody>, `barHeight` tall, makes room for the bar.
 */
export function useTopScrollbar() {
  const wrapEl = ref<HTMLElement | null>(null)
  const headEl = ref<HTMLElement | null>(null)
  const topScrollEl = ref<HTMLElement | null>(null)
  const showBar = ref(false)
  const contentWidth = ref(0)
  // Where the bar goes: the box's 1px top border plus the heading row.
  const barTop = ref(0)
  const barHeight = ref(0)

  const measure = () => {
    const wrap = wrapEl.value
    if (!wrap) {
      showBar.value = false
      return
    }
    // The table's own height, leaving out the gap the bar adds.
    const height = wrap.offsetHeight - (showBar.value ? barHeight.value : 0)
    showBar.value = wrap.scrollWidth > wrap.clientWidth + 1 && height > window.innerHeight
    contentWidth.value = wrap.scrollWidth
    barTop.value = 1 + (headEl.value?.offsetHeight ?? 0)
    // Shown or hidden only after this render, so measured on the next frame.
    requestAnimationFrame(() => {
      barHeight.value = topScrollEl.value?.offsetHeight ?? 0
      if (topScrollEl.value) topScrollEl.value.scrollLeft = wrap.scrollLeft
    })
  }

  const syncFromTable = () => {
    if (wrapEl.value && topScrollEl.value) topScrollEl.value.scrollLeft = wrapEl.value.scrollLeft
  }

  const syncFromTop = () => {
    if (wrapEl.value && topScrollEl.value) wrapEl.value.scrollLeft = topScrollEl.value.scrollLeft
  }

  let observer: ResizeObserver | null = null
  // The table can come and go (loading, a collapsed section), so the box,
  // its table and the heading row are watched again whenever they change.
  watch(
    [wrapEl, headEl],
    ([wrap, head]) => {
      observer?.disconnect()
      measure()
      if (!wrap || typeof ResizeObserver === 'undefined') return
      observer ??= new ResizeObserver(measure)
      observer.observe(wrap)
      const table = wrap.querySelector('table')
      if (table) observer.observe(table)
      if (head) observer.observe(head)
    },
    { flush: 'post' },
  )
  // The window's height changes nothing the observer sees.
  window.addEventListener('resize', measure)
  onScopeDispose(() => {
    observer?.disconnect()
    window.removeEventListener('resize', measure)
  })

  return {
    wrapEl,
    headEl,
    topScrollEl,
    showBar,
    contentWidth,
    barTop,
    barHeight,
    syncFromTable,
    syncFromTop,
  }
}
