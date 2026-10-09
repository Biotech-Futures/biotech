import { ref } from 'vue'

/**
 * True while a marking tab that benefits from the full browser width is
 * active (SAQs & Poster, SAQ, Poster, Report — not Prototype). The marking
 * page sets it per tab and resets it on unmount; App.vue lifts the layout's
 * centre max-width while it holds.
 */
export const markingFullWidth = ref(false)
