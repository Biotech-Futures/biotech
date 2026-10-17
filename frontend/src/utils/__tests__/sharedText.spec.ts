import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as Y from 'yjs'
import { EASE_MS, SharedTextField, diffAt, moveThrough } from '@/utils/sharedText'

let now = 0
let frames: FrameRequestCallback[] = []

/** Runs animation frames up to `ms` from now. */
function advance(ms: number) {
  const end = now + ms
  while (now < end) {
    now = Math.min(end, now + 16)
    const due = frames
    frames = []
    due.forEach((callback) => callback(now))
  }
}

beforeEach(() => {
  now = 0
  frames = []
  vi.spyOn(performance, 'now').mockImplementation(() => now)
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => frames.push(callback))
  vi.stubGlobal('cancelAnimationFrame', () => {
    frames = []
  })
})

describe('diffAt', () => {
  it('finds an insertion, a deletion and a replacement', () => {
    expect(diffAt('hello world', 'hello big world', 10)).toEqual({ start: 6, removed: 0, inserted: 'big ' })
    expect(diffAt('hello big world', 'hello world', 6)).toEqual({ start: 6, removed: 4, inserted: '' })
    expect(diffAt('hello world', 'hello there', 11)).toEqual({ start: 6, removed: 5, inserted: 'there' })
  })

  it('places an ambiguous edit at the caret', () => {
    // Typing "a" at the start of "aa": the text alone would say it went at the end.
    expect(diffAt('aa', 'aaa', 1)).toEqual({ start: 0, removed: 0, inserted: 'a' })
    expect(diffAt('aa', 'aaa', 3)).toEqual({ start: 2, removed: 0, inserted: 'a' })
  })
})

describe('moveThrough', () => {
  it('moves a caret past text inserted or deleted before it, and not after it', () => {
    expect(moveThrough(5, [{ insert: 'abc' }])).toBe(8)
    expect(moveThrough(5, [{ retain: 5 }, { insert: 'abc' }])).toBe(5)
    expect(moveThrough(5, [{ delete: 2 }])).toBe(3)
    expect(moveThrough(5, [{ retain: 3 }, { delete: 10 }])).toBe(3)
    expect(moveThrough(5, [{ retain: 9 }, { delete: 2 }])).toBe(5)
  })
})

/** Two people's copies of one document, kept in step the way the server relays updates. */
function pair(initial = '') {
  const a = new Y.Doc()
  const b = new Y.Doc()
  a.getText('t').insert(0, initial)
  Y.applyUpdate(b, Y.encodeStateAsUpdate(a))
  a.on('update', (update: Uint8Array, origin: unknown) => {
    if (origin !== 'relay') Y.applyUpdate(b, update, 'relay')
  })
  b.on('update', (update: Uint8Array, origin: unknown) => {
    if (origin !== 'relay') Y.applyUpdate(a, update, 'relay')
  })
  return { a, b }
}

const fields: SharedTextField[] = []
const boxes: HTMLTextAreaElement[] = []

function bind(doc: Y.Doc) {
  const box = document.createElement('textarea')
  document.body.appendChild(box)
  boxes.push(box)
  const shown: string[] = []
  const displayed: string[] = []
  const field = new SharedTextField(
    doc.getText('t'),
    {},
    () => box,
    (value) => shown.push(value),
    (value) => displayed.push(value)
  )
  fields.push(field)
  box.value = field.value
  return { box, field, shown, displayed }
}

function type(box: HTMLTextAreaElement, field: SharedTextField, at: number, text: string) {
  box.focus()
  box.value = box.value.slice(0, at) + text + box.value.slice(at)
  box.setSelectionRange(at + text.length, at + text.length)
  field.input(box)
}

afterEach(() => {
  fields.splice(0).forEach((field) => field.destroy())
  boxes.splice(0).forEach((box) => box.remove())
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('SharedTextField', () => {
  it("shows each person's typing to the other", () => {
    const { a, b } = pair('hello world')
    const ada = bind(a)
    const ben = bind(b)

    type(ada.box, ada.field, 5, ',')
    type(ben.box, ben.field, 12, '!')

    expect(ada.box.value).toBe('hello, world!')
    expect(ben.box.value).toBe('hello, world!')
  })

  it("keeps the caret in place when a teammate types before it", () => {
    const { a, b } = pair('world')
    const ada = bind(a)
    const ben = bind(b)
    ada.box.focus()
    ada.box.setSelectionRange(5, 5)

    b.getText('t').insert(0, 'hello ')
    advance(EASE_MS)

    expect(ada.box.value).toBe('hello world')
    expect(ada.box.selectionStart).toBe(11)
    expect(ben.box.value).toBe('hello world')
  })

  it("undoes only this person's typing, never a teammate's", () => {
    const { a, b } = pair('')
    const ada = bind(a)
    bind(b)

    type(ada.box, ada.field, 0, 'mine')
    b.getText('t').insert(4, ' theirs')
    const undo = new KeyboardEvent('keydown', { key: 'z', ctrlKey: true })
    expect(ada.field.keydown(undo)).toBe(true)

    expect(a.getText('t').toString()).toBe(' theirs')
    expect(b.getText('t').toString()).toBe(' theirs')
  })

  it('applies composed text where composing began, even after a teammate edits earlier on', () => {
    const { a, b } = pair('ab')
    const ada = bind(a)
    ada.box.focus()
    ada.box.setSelectionRange(2, 2)
    ada.field.startComposition(ada.box)

    b.getText('t').insert(0, 'XY')
    // The box is left alone while composing, so it still shows the old text plus the composition.
    ada.box.value = 'ab日本'
    ada.box.setSelectionRange(4, 4)
    ada.field.endComposition(ada.box)

    expect(a.getText('t').toString()).toBe('XYab日本')
    expect(b.getText('t').toString()).toBe('XYab日本')
    expect(ada.box.value).toBe('XYab日本')
  })

  it('reports every value it shows', () => {
    const { a, b } = pair('x')
    const ada = bind(a)

    b.getText('t').insert(1, 'y')

    expect(ada.shown.at(-1)).toBe('xy')
  })

  it("types a teammate's text out in a box nobody here is typing in, and saves it once shown", () => {
    const { a, b } = pair('Our ')
    const ada = bind(a)
    bind(b)

    b.getText('t').insert(4, 'idea is')
    expect(ada.box.value).toBe('Our ')
    advance(EASE_MS / 2)
    expect(ada.box.value.length).toBeGreaterThan('Our '.length)
    expect(ada.box.value.length).toBeLessThan('Our idea is'.length)
    expect(ada.shown).not.toContain('Our idea is')
    advance(EASE_MS)

    expect(ada.box.value).toBe('Our idea is')
    expect(ada.shown.at(-1)).toBe('Our idea is')
    expect(ada.displayed.length).toBeGreaterThan(2)
  })

  it('never eases text into the box being typed in', () => {
    const { a, b } = pair('Our ')
    const ada = bind(a)
    ada.box.focus()

    b.getText('t').insert(4, 'idea is')

    expect(ada.box.value).toBe('Our idea is')
  })

  it('shows all of the text at once when the box gains focus mid-way', () => {
    const { a, b } = pair('Our ')
    const ada = bind(a)
    b.getText('t').insert(4, 'idea is')
    advance(EASE_MS / 2)

    ada.field.settle()

    expect(ada.box.value).toBe('Our idea is')
    expect(ada.shown.at(-1)).toBe('Our idea is')
    advance(EASE_MS)
    expect(ada.box.value).toBe('Our idea is')
  })

  it("keeps a teammate's cursor in place as text is typed before it", () => {
    const { a, b } = pair('hello world')
    const ada = bind(a)
    const ben = bind(b)
    ben.box.focus()
    ben.box.setSelectionRange(6, 6)
    const at = ben.field.cursorAt()!

    a.getText('t').insert(0, 'Oh, ')
    advance(EASE_MS)

    expect(ada.field.positionOf(at)).toBe(10)
  })

  it('places a cursor among text still easing in where it shows', () => {
    const { a, b } = pair('ab')
    const ada = bind(a)
    const ben = bind(b)

    b.getText('t').insert(2, 'cdef')
    ben.field.settle()
    ben.box.focus()
    ben.box.setSelectionRange(6, 6)
    const atEnd = ben.field.cursorAt()!
    advance(EASE_MS / 2)

    expect(ada.field.positionOf(atEnd)).toBe(ada.box.value.length)
  })

  it('has no cursor to share outside the box, and ignores one from another text', () => {
    const { a, b } = pair('hello')
    const ada = bind(a)
    bind(b)
    const encode = (text: Y.Text, index: number) =>
      btoa(String.fromCharCode(...Y.encodeRelativePosition(Y.createRelativePositionFromTypeIndex(text, index))))
    const other = new Y.Doc()
    other.getText('t').insert(0, 'xy')

    expect(ada.field.cursorAt()).toBeNull()
    expect(ada.field.positionOf(encode(a.getText('answer:q2'), 0))).toBeNull()
    expect(ada.field.positionOf(encode(other.getText('t'), 1))).toBeNull()
    expect(ada.field.positionOf('%%%')).toBeNull()
  })
})
