import * as Y from 'yjs'

type Field = HTMLInputElement | HTMLTextAreaElement
type Delta = Array<{ insert?: unknown; delete?: number; retain?: number }>

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
  private readonly undoManager: Y.UndoManager
  private readonly observer: (event: Y.YTextEvent, transaction: Y.Transaction) => void

  constructor(
    private readonly text: Y.Text,
    private readonly origin: object,
    private readonly element: () => Field | null,
    private readonly onValue: (value: string) => void
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
    const value = this.text.toString()
    const field = this.element()
    if (field && !this.composition && field.value !== value) {
      const focused = typeof document !== 'undefined' && document.activeElement === field
      const start = field.selectionStart ?? 0
      const end = field.selectionEnd ?? 0
      field.value = value
      if (focused) {
        const caret = delta ? [moveThrough(start, delta), moveThrough(end, delta)] : [start, end]
        field.setSelectionRange(Math.min(caret[0], value.length), Math.min(caret[1], value.length))
      }
    }
    // While composing, the box keeps the composed text; it catches up when composing ends.
    if (!this.composition) this.onValue(value)
  }
}
