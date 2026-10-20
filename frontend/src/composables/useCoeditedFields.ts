import { computed, effectScope, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { useLiveRoom } from '@/composables/useLiveRoom'
import { useSharedDoc } from '@/composables/useSharedDoc'
import { SharedTextField } from '@/utils/sharedText'

/** How long the live connection may take before typing carries on without it. */
export const LIVE_FALLBACK_MS = 10_000
/** How often a page saving without the live connection brings in the team's saved changes. */
export const FALLBACK_CATCH_UP_MS = 10_000

/** A teammate's cursor, by where it falls in a box's shown text. */
export interface PlacedCursor {
  id: number
  name: string
  index: number
  /** When their current run of typing began. */
  startedAt: number | null
}

/** One box's teammates' cursors, and what the box shows. */
export interface CursorSource {
  target: () => HTMLInputElement | HTMLTextAreaElement | null
  text: Ref<string>
  cursors: Ref<PlacedCursor[]>
}

type Box = HTMLInputElement | HTMLTextAreaElement

export interface CoeditedFieldsOptions {
  live: ReturnType<typeof useLiveRoom>
  coediting: Ref<boolean>
  /** An admin edits privately, as without co-editing. */
  adminAccess: Ref<boolean>
  isEditable: Ref<boolean>
  /** The ids of the boxes typed into, which are also the field names the page shares. */
  boxes: Ref<string[]>
  /** The shared document's name for a box's text. */
  sharedName: (box: string) => string
  /** Whether a box may take the shared text now, e.g. not while it shows the submitted copy. */
  mayShow: () => boolean
  /** Puts the shared text in a box; the server saves it, so it counts as saved. */
  showSaved: (box: string, value: string) => void
  /** Without the live connection the page saves as without co-editing, through these. */
  fallback: {
    /** Runs a change that should not make the page count as unsaved if it was saved before. */
    keepSaved: (change: () => void) => void
    /** Saves what was typed; true once nothing is left unsaved. */
    saveTyping: () => Promise<boolean>
    /** Brings in the team's saved changes to boxes not being edited. */
    catchUp: () => Promise<void>
  }
}

/**
 * The page's typing boxes bound to the team's shared document: what they show, the edits typed into
 * them, teammates' cursors, and saving as without co-editing when the live connection cannot be made.
 */
export function useCoeditedFields(options: CoeditedFieldsOptions) {
  const { live, coediting, adminAccess, isEditable, boxes, fallback } = options
  const shared = useSharedDoc(live, coediting)
  /** Marks edits typed on this page, so undo covers this person's typing only. */
  const typedHere = {}
  const bound = new Map<string, SharedTextField>()

  const teamCoediting = computed(() => coediting.value && !adminAccess.value)
  /** The live connection could not be made, so this person types and saves as without co-editing. */
  const liveUnavailable = ref(false)
  const typingShared = computed(() => teamCoediting.value && !liveUnavailable.value)
  const savingWithoutLive = computed(() => teamCoediting.value && liveUnavailable.value)
  /** Read-only until the shared document has arrived and the server allows editing it. */
  const textEditable = computed(
    () => isEditable.value && (!typingShared.value || (shared.synced.value && shared.editable.value))
  )
  const note = computed(() => {
    if (!teamCoediting.value || !isEditable.value) return ''
    if (liveUnavailable.value) {
      return "Live editing isn't available on this connection. Your changes are still saved, and your team's appear every few seconds."
    }
    if (!shared.synced.value) return "Connecting to your team's live answers…"
    return shared.editable.value ? '' : "Your team's answers can't be edited right now."
  })

  // ---- Binding boxes to the shared text --------------------------------------------------

  /** Bumped as boxes are bound to a new copy of the document, so cursors are placed in it. */
  const bindings = ref(0)
  /** The box this person's cursor was last shared in, so leaving it can clear it for teammates. */
  let cursorBox: string | null = null
  const cursorScope = effectScope()
  const cursorSources = new Map<string, CursorSource>()

  function bind() {
    bound.forEach((field) => field.destroy())
    bound.clear()
    // Without the live connection the boxes are the page's own, so a returning shared copy cannot overwrite them.
    if (!coediting.value || liveUnavailable.value) return
    for (const box of boxes.value) {
      const source = cursorSource(box)
      const field = new SharedTextField(
        shared.text(options.sharedName(box)),
        typedHere,
        source.target,
        (value) => show(box, value),
        (value) => (source.text.value = value)
      )
      bound.set(box, field)
      source.text.value = field.value
    }
    bindings.value += 1
    // A new copy of the document: this person's cursor is placed in it afresh.
    if (cursorBox) shareCursor(cursorBox)
  }

  function show(box: string, value: string) {
    // A half-arrived document, or typing saved without the live connection, is not shown over.
    if (!options.mayShow() || !shared.synced.value || liveUnavailable.value) return
    options.showSaved(box, value)
  }

  function showAll() {
    bound.forEach((field, box) => show(box, field.value))
  }

  shared.onReplaced(() => bind())
  // Bound again only when the boxes themselves change, not on every refresh, so undo history and
  // text easing in survive a teammate's tick or upload.
  watch([coediting, () => boxes.value.join('|')], () => bind(), { immediate: true })
  watch(
    () => shared.synced.value,
    (synced) => {
      if (synced) showAll()
    }
  )

  // ---- Cursors ---------------------------------------------------------------------------

  /** What a box shows and where teammates' cursors fall in it, for the cursors drawn over it. */
  function cursorSource(box: string): CursorSource {
    const existing = cursorSources.get(box)
    if (existing) return existing
    const text: Ref<string> = ref('')
    const cursors = cursorScope.run(() =>
      computed<PlacedCursor[]>(() => {
        void text.value
        void bindings.value
        const field = bound.get(box)
        if (!field || !typingShared.value) return []
        return live.cursorsIn(box).flatMap((cursor) => {
          const index = field.positionOf(cursor.at)
          return index === null ? [] : [{ id: cursor.id, name: cursor.name, index, startedAt: cursor.startedAt }]
        })
      })
    )!
    const source: CursorSource = { target: () => document.getElementById(box) as Box | null, text, cursors }
    cursorSources.set(box, source)
    return source
  }

  /** Shares where this person's cursor is in `box`; `typed` when typing moved it. */
  function shareCursor(box: string, typed = false) {
    if (!typingShared.value || !textEditable.value) return
    const at = bound.get(box)?.cursorAt()
    if (!at) return
    cursorBox = box
    live.sendCursor(box, at, typed)
  }

  function enterField(box: string) {
    // Text still easing in is shown in full first, so typing starts from all of it.
    bound.get(box)?.settle()
    shareCursor(box)
  }

  function leaveField(box: string) {
    if (cursorBox !== box) return
    cursorBox = null
    live.sendCursor(box, null)
  }

  // Submitting or the deadline makes the boxes read-only, so the cursor goes too.
  watch(textEditable, (editable) => {
    if (!editable && cursorBox) leaveField(cursorBox)
  })

  // ---- Typing ----------------------------------------------------------------------------

  /** A box's input; true when it went into the shared document. */
  function input(box: string, event: Event): boolean {
    if (!typingShared.value) return false
    bound.get(box)?.input(event.target as Box)
    live.sendTyping(box)
    shareCursor(box, true)
    return true
  }

  function startComposing(box: string, event: CompositionEvent) {
    if (typingShared.value) bound.get(box)?.startComposition(event.target as Box)
  }

  function endComposing(box: string, event: CompositionEvent) {
    if (typingShared.value) bound.get(box)?.endComposition(event.target as Box)
  }

  function onFieldKeydown(box: string, event: KeyboardEvent) {
    if (typingShared.value) bound.get(box)?.keydown(event)
  }

  // ---- Without the live connection -------------------------------------------------------

  let fallbackTimer: ReturnType<typeof setTimeout> | null = null
  let fallbackCatchUp: ReturnType<typeof setInterval> | null = null
  let leavingFallback = false

  /** Waits for the live connection while the boxes are read-only, and switches back once it is made. */
  function checkLiveConnection() {
    const waiting =
      typingShared.value && isEditable.value && !shared.synced.value && document.visibilityState === 'visible'
    if (!waiting && fallbackTimer) {
      clearTimeout(fallbackTimer)
      fallbackTimer = null
    }
    if (waiting && !fallbackTimer) fallbackTimer = setTimeout(startSavingWithoutLive, LIVE_FALLBACK_MS)
    if (savingWithoutLive.value && shared.synced.value) void stopSavingWithoutLive()
  }

  function startSavingWithoutLive() {
    fallbackTimer = null
    // The boxes become the page's own copy, as without co-editing, starting out saved.
    fallback.keepSaved(() => {
      liveUnavailable.value = true
      bind()
    })
    void fallback.catchUp()
  }

  /** Back on the live connection: typing done meanwhile is saved first, then the shared copy takes over. */
  async function stopSavingWithoutLive() {
    if (leavingFallback) return
    leavingFallback = true
    try {
      // A failed save, or typing that landed meanwhile, keeps this page as it is until the next try.
      if (!(await fallback.saveTyping()) || !shared.synced.value) return
      liveUnavailable.value = false
      shared.restart()
    } finally {
      leavingFallback = false
    }
  }

  watch([typingShared, isEditable, () => shared.synced.value], checkLiveConnection, { immediate: true })
  document.addEventListener('visibilitychange', checkLiveConnection)
  watch(savingWithoutLive, (on) => {
    if (fallbackCatchUp) clearInterval(fallbackCatchUp)
    fallbackCatchUp = on
      ? setInterval(() => void (shared.synced.value ? stopSavingWithoutLive() : fallback.catchUp()), FALLBACK_CATCH_UP_MS)
      : null
  })

  onBeforeUnmount(() => {
    if (fallbackTimer) clearTimeout(fallbackTimer)
    if (fallbackCatchUp) clearInterval(fallbackCatchUp)
    document.removeEventListener('visibilitychange', checkLiveConnection)
    cursorScope.stop()
    bound.forEach((field) => field.destroy())
  })

  return {
    shared,
    typingShared,
    savingWithoutLive,
    textEditable,
    note,
    showAll,
    cursorSource,
    shareCursor,
    enterField,
    leaveField,
    input,
    startComposing,
    endComposing,
    onFieldKeydown
  }
}
