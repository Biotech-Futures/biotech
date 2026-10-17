import * as Y from 'yjs'
import { fromBase64, toBase64 } from '@/composables/useSharedDoc'

type Field = HTMLInputElement | HTMLTextAreaElement
type Delta = Array<{ insert?: unknown; delete?: number; retain?: number }>

/** A teammate's new text is typed out over about the gap between their updates. */
export const EASE_MS = 100

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

/** The one stretch of text a change adds, or null for anything else (deletions, several edits). */
function insertionIn(delta: Delta | null): { at: number; text: string } | null {
  if (!delta) return null
  const ops = delta[0]?.retain ? delta.slice(1) : delta
  const inserted = ops[0]?.insert
  if (ops.length !== 1 || typeof inserted !== 'string') return null
  return { at: delta[0]?.retain ?? 0, text: inserted }
}

/**
 * The single edit that turns `before` into `after`, placed at the caret where the text alone is
 * ambiguous (typing "a" into "aa" could have gone anywhere).
 */
export function diffAt(before: string, after: string, caret: number) {
  // Typed text ends at the caret, so the edit can start no later than the caret less what was added.
  const grown = Math.max(0, after.length - before.length)
  const startLimit = Math.max(0, Math.min(before.length, after.length, caret - grown))
  let start = 0
  while (start < startLimit && before[start] === after[start]) start += 1
  // The unchanged tail may not reach back past the caret, so the edit lands where it was made.
  const tailLimit = Math.min(before.length - start, after.length - start, Math.max(0, after.length - caret))
  let tail = 0
  while (tail < tailLimit && before[before.length - 1 - tail] === after[after.length - 1 - tail]) tail += 1
  return {
    start,
    removed: before.length - start - tail,
    inserted: after.slice(start, after.length - tail)
  }
}

/** Where a position in the old text ends up once a remote change is applied. */
export function moveThrough(index: number, delta: Delta): number {
  let oldPos = 0
  let result = index
  for (const op of delta) {
    if (op.retain) {
      oldPos += op.retain
    } else if (op.insert !== undefined) {
      if (oldPos < index) result += typeof op.insert === 'string' ? op.insert.length : 1
    } else if (op.delete) {
      if (oldPos < index) result -= Math.min(op.delete, index - oldPos)
      oldPos += op.delete
    }
  }
  return Math.max(0, result)
}

interface Easing {
  at: number
  added: string
  shown: number
  value: string
  frame: number
}

interface Composition {
  base: string
  start: number
  end: number
  from: Y.RelativePosition
  to: Y.RelativePosition
}

/**
 * One text box bound to a shared Y.Text. Typing here becomes edits to the shared text; edits from
 * elsewhere update the box without moving the caret; undo and redo cover only this person's typing.
 */
export class SharedTextField {
  private composition: Composition | null = null
  private easing: Easing | null = null
  private readonly undoManager: Y.UndoManager
  private readonly observer: (event: Y.YTextEvent, transaction: Y.Transaction) => void

  constructor(
    private readonly text: Y.Text,
    private readonly origin: object,
    private readonly element: () => Field | null,
    private readonly onValue: (value: string) => void,
    /** Whatever the box shows, as it shows it, including while a teammate's text eases in. */
    private readonly onShown: (value: string) => void = () => {}
  ) {
    this.undoManager = new Y.UndoManager(text, { trackedOrigins: new Set([origin]), captureTimeout: 500 })
    this.observer = (event, transaction) => {
      if (transaction.origin !== this.origin) this.showChange(event.delta as Delta)
    }
    text.observe(this.observer)
  }

  get value(): string {
    return this.text.toString()
  }

  /** The box's input event: whatever changed becomes one edit to the shared text. */
  input(field: Field) {
    if (this.composition) return
    const before = this.text.toString()
    const after = field.value
    if (before === after) return
    const { start, removed, inserted } = diffAt(before, after, field.selectionEnd ?? after.length)
    this.edit(start, removed, inserted)
    this.onValue(after)
    this.onShown(after)
  }

  /** Shows any text still easing in at once, e.g. as the box gains focus, so typing starts from all of it. */
  settle() {
    const easing = this.easing
    if (!easing) return
    cancelAnimationFrame(easing.frame)
    this.easing = null
    const field = this.element()
    if (field) field.value = easing.value
    this.onValue(easing.value)
    this.onShown(easing.value)
  }

  /** Where in the box's shown text a place in the shared text is, allowing for text still easing in. */
  displayIndex(index: number): number {
    const easing = this.easing
    if (!easing) return index
    const hidden = easing.added.length - easing.shown
    if (index <= easing.at) return index
    if (index >= easing.at + easing.added.length) return index - hidden
    return Math.min(index, easing.at + easing.shown)
  }

  /** This person's cursor as a shared position, so teammates see it stay put as text changes; null when not in the box. */
  cursorAt(): string | null {
    const field = this.element()
    if (!field || typeof document === 'undefined' || document.activeElement !== field) return null
    const index = Math.min(field.selectionEnd ?? field.value.length, this.text.length)
    return toBase64(Y.encodeRelativePosition(Y.createRelativePositionFromTypeIndex(this.text, index)))
  }

  /** Where a teammate's cursor falls in the box's shown text; null if it is not in this text. */
  positionOf(at: string): number | null {
    const doc = this.text.doc
    const bytes = fromBase64(at)
    if (!doc || !bytes) return null
    try {
      const position = Y.createAbsolutePositionFromRelativePosition(Y.decodeRelativePosition(bytes), doc)
      if (!position || position.type !== this.text) return null
      return this.displayIndex(position.index)
    } catch {
      return null
    }
  }

  /** An input method (e.g. for Chinese or Japanese) has started composing; the box is left alone until it ends. */
  startComposition(field: Field) {
    const start = Math.min(field.selectionStart ?? 0, this.text.length)
    const end = Math.min(field.selectionEnd ?? start, this.text.length)
    this.composition = {
      base: field.value,
      start,
      end,
      from: Y.createRelativePositionFromTypeIndex(this.text, start),
      to: Y.createRelativePositionFromTypeIndex(this.text, end)
    }
  }

  endComposition(field: Field) {
    const composition = this.composition
    this.composition = null
    const doc = this.text.doc
    const after = field.value
    if (!composition || !doc) {
      this.input(field)
      return
    }
    const { base, start, end } = composition
    const from = Y.createAbsolutePositionFromRelativePosition(composition.from, doc)
    const to = Y.createAbsolutePositionFromRelativePosition(composition.to, doc)
    const tail = base.length - end
    const asExpected =
      after.length >= start + tail && after.startsWith(base.slice(0, start)) && after.endsWith(base.slice(end))
    if (from && to && asExpected) {
      // The selection made when composing began is replaced, wherever teammates' edits have since moved it.
      this.edit(from.index, Math.max(0, to.index - from.index), after.slice(start, after.length - tail))
    } else {
      const { start: at, removed, inserted } = diffAt(this.text.toString(), after, field.selectionEnd ?? after.length)
      this.edit(at, removed, inserted)
    }
    this.showChange(null)
  }

  /** Ctrl/Cmd+Z and Ctrl/Cmd+Y (or Shift+Z): true when the key was handled here. */
  keydown(event: KeyboardEvent): boolean {
    if (!(event.ctrlKey || event.metaKey) || this.composition) return false
    const key = event.key.toLowerCase()
    if (key === 'z' && !event.shiftKey) {
      event.preventDefault()
      this.undoManager.undo()
      return true
    }
    if (key === 'y' || (key === 'z' && event.shiftKey)) {
      event.preventDefault()
      this.undoManager.redo()
      return true
    }
    return false
  }

  destroy() {
    if (this.easing) cancelAnimationFrame(this.easing.frame)
    this.easing = null
    this.text.unobserve(this.observer)
    this.undoManager.destroy()
  }

  private edit(start: number, removed: number, inserted: string) {
    const doc = this.text.doc
    if (!doc || (!removed && !inserted)) return
    const length = this.text.length
    const at = Math.min(Math.max(0, start), length)
    doc.transact(() => {
      if (removed) this.text.delete(at, Math.min(removed, length - at))
      if (inserted) this.text.insert(at, inserted)
    }, this.origin)
  }

  /** Shows the shared text in the box, keeping the caret where it was; a null delta just refreshes. */
  private showChange(delta: Delta | null) {
    this.settle()
    const value = this.text.toString()
    const field = this.element()
    if (field && !this.composition && field.value !== value) {
      const focused = typeof document !== 'undefined' && document.activeElement === field
      // Eased in only where nobody here is typing, so it never fights a keystroke.
      const added = focused ? null : insertionIn(delta)
      if (added && added.text.length > 1 && !reducedMotion()) {
        const before = value.slice(0, added.at) + value.slice(added.at + added.text.length)
        if (field.value === before) {
          this.ease(field, value, added.at, added.text)
          return
        }
      }
      const start = field.selectionStart ?? 0
      const end = field.selectionEnd ?? 0
      field.value = value
      if (focused) {
        const caret = delta ? [moveThrough(start, delta), moveThrough(end, delta)] : [start, end]
        field.setSelectionRange(Math.min(caret[0], value.length), Math.min(caret[1], value.length))
      }
    }
    // While composing, the box keeps the composed text; it catches up when composing ends.
    if (!this.composition) {
      this.onValue(value)
      this.onShown(field?.value ?? value)
    }
  }

  private ease(field: Field, value: string, at: number, added: string) {
    const began = performance.now()
    const easing: Easing = { at, added, shown: 0, value, frame: 0 }
    const step = (now: number) => {
      const progress = Math.min(1, (now - began) / EASE_MS)
      easing.shown = Math.ceil(added.length * progress)
      field.value = value.slice(0, at) + added.slice(0, easing.shown) + value.slice(at + added.length)
      if (progress < 1) {
        this.onShown(field.value)
        easing.frame = requestAnimationFrame(step)
      } else {
        this.settle()
      }
    }
    this.easing = easing
    easing.frame = requestAnimationFrame(step)
  }
}
