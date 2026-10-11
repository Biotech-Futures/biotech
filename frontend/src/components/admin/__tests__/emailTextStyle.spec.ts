import { describe, expect, it } from 'vitest'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { EmailBox, EmailButton } from '@/components/admin/emailBlocks'
import {
  EmailTextStyle,
  EmailTextStyles,
  gapBelowSelection,
  marginOf,
  styleValue,
  textStyleAt
} from '@/components/admin/emailTextStyle'

/** What the System Emails editor makes of some HTML. */
const edit = (html: string, change?: (editor: Editor) => void) => {
  const editor = new Editor({
    extensions: [StarterKit, EmailBox, EmailButton, EmailTextStyle, EmailTextStyles],
    content: html
  })
  change?.(editor)
  const out = editor.getHTML()
  editor.destroy()
  return out
}

/** The element ``selector`` picks out of ``html``, to read its style. */
const find = (html: string, selector: string) => {
  const holder = document.createElement('div')
  holder.innerHTML = html
  return holder.querySelector<HTMLElement>(selector)
}

describe('email text keeps its colours and sizes', () => {
  it("keeps a paragraph's colour, size and spacing", () => {
    const out = edit('<p style="margin:0 0 8px 0; color:#6d7a72; font-size:14px; line-height:1.5;">Hi Pat,</p>')

    const p = find(out, 'p')!
    expect(p.style.color).toBe('rgb(109, 122, 114)')
    expect(p.style.fontSize).toBe('14px')
    expect(p.style.lineHeight).toBe('1.5')
    expect(p.style.marginBottom).toBe('8px')
  })

  it('keeps a green word inside a heading', () => {
    const out = edit(
      '<h1 style="margin:0; color:#1a2e23; font-size:26px;">Your action is required for a recent ' +
        '<span style="color:#307054;">BIOTech Futures</span> registration.</h1>'
    )

    expect(find(out, 'h1')!.style.fontSize).toBe('26px')
    const word = find(out, 'h1 span')!
    expect(word.textContent).toBe('BIOTech Futures')
    expect(word.style.color).toBe('rgb(48, 112, 84)')
  })

  it('keeps the style on bold text, links, lists and dividers', () => {
    const out = edit(
      '<p><strong style="color:#017151">Note</strong> <a href="https://example.org" style="color:#307054; font-weight:600">link</a></p>' +
        '<ul style="margin:0 0 14px 22px"><li style="margin:6px 0"><p>One</p></li></ul>' +
        '<hr style="border:none; height:1px; background:#e0e4e1">'
    )

    expect(find(out, 'strong')!.style.color).toBe('rgb(1, 113, 81)')
    expect(find(out, 'a')!.style.fontWeight).toBe('600')
    expect(find(out, 'ul')!.style.marginLeft).toBe('22px')
    expect(find(out, 'li')!.style.margin).toBe('6px 0px')
    const hr = find(out, 'hr')!
    expect(hr.style.height).toBe('1px')
    expect(hr.style.backgroundColor).toBe('rgb(224, 228, 225)')
  })

  it("drops the styles the server doesn't keep", () => {
    const out = edit('<p style="position:absolute; color:#1a2e23">Text</p>')

    const p = find(out, 'p')!
    expect(p.style.position).toBe('')
    expect(p.style.color).toBe('rgb(26, 46, 35)')
  })

  it('leaves a plain span as plain text', () => {
    expect(edit('<p><span>plain</span></p>')).toBe('<p>plain</p>')
  })
})

describe('colouring and resizing selected text', () => {
  const selectHello = (editor: Editor) => editor.commands.setTextSelection({ from: 1, to: 6 })

  it('colours the selected text, and No colour takes it off', () => {
    const coloured = edit('<p>Hello world</p>', (editor) => {
      selectHello(editor)
      editor.commands.setTextColour('#307054')
    })
    const span = find(coloured, 'span')!
    expect(span.textContent).toBe('Hello')
    expect(span.style.color).toBe('rgb(48, 112, 84)')

    const plain = edit(coloured, (editor) => {
      selectHello(editor)
      editor.commands.setTextColour(null)
    })
    expect(plain).toBe('<p>Hello world</p>')
  })

  it('resizes the selected text and keeps its colour', () => {
    const out = edit('<p>Hello world</p>', (editor) => {
      selectHello(editor)
      editor.commands.setTextColour('#307054')
      editor.commands.setTextSize('12px')
    })
    const span = find(out, 'span')!
    expect(span.style.fontSize).toBe('12px')
    expect(span.style.color).toBe('rgb(48, 112, 84)')

    const normal = edit(out, (editor) => {
      selectHello(editor)
      editor.commands.setTextSize(null)
    })
    const kept = find(normal, 'span')!
    expect(kept.style.fontSize).toBe('')
    expect(kept.style.color).toBe('rgb(48, 112, 84)')
  })
})

describe('the gap below a paragraph', () => {
  // Three paragraphs, each 14px apart; the cursor in the second ("Two").
  const THREE =
    '<p style="margin:0 0 14px 0">One</p><p style="margin:0 0 14px 0">Two</p><p style="margin:14px 0 0 0">Three</p>'
  const inTwo = (editor: Editor) => editor.commands.setTextSelection(7)

  it('sets the gap below the selected paragraph and nowhere else', () => {
    const out = edit(THREE, (editor) => {
      inTwo(editor)
      editor.commands.setGapBelow('24px')
    })
    const [one, two, three] = Array.from(find(`<div>${out}</div>`, 'div')!.querySelectorAll<HTMLElement>('p'))
    // The gap below Two: its own bottom margin, with Three's top margin cleared.
    expect(two.style.marginBottom).toBe('24px')
    expect(three.style.marginTop).toBe('0px')
    // The gap above Two is untouched.
    expect(one.style.marginBottom).toBe('14px')
    expect(two.style.marginTop).toBe('0px')
  })

  it('reads the gap below the selected paragraph', () => {
    const editor = new Editor({
      extensions: [StarterKit, EmailTextStyle, EmailTextStyles],
      content: '<p style="margin:0 0 24px 0">Hi Pat,</p><h1 style="margin:0">Heading</h1>'
    })
    editor.commands.setTextSelection(2)
    expect(gapBelowSelection(editor.state)).toBe('24px')
    editor.commands.setGapBelow('8px')
    expect(gapBelowSelection(editor.state)).toBe('8px')
    editor.destroy()
  })

  const BUTTON =
    '<div class="email-button" style="margin:20px 0; text-align:left">' +
    '<a class="cta-link" href="https://example.org" style="display:inline-block; background-color:#017151">Go</a></div>'

  it('sets the gap below a button, and above it from the paragraph before', () => {
    // "Text" is 1 to 5, the button's text starts at 7.
    const below = edit(`<p>Text</p>${BUTTON}<p>After</p>`, (editor) => {
      editor.commands.setTextSelection(7)
      editor.commands.setGapBelow('8px')
    })
    const wrapper = find(below, 'div.email-button')!
    expect(wrapper.style.marginBottom).toBe('8px')
    expect(wrapper.style.marginTop).toBe('20px')
    expect(find(below, 'div.email-button + p')!.style.marginTop).toBe('0px')

    const above = edit(`<p>Text</p>${BUTTON}`, (editor) => {
      editor.commands.setTextSelection(2)
      editor.commands.setGapBelow('24px')
    })
    expect(find(above, 'p')!.style.marginBottom).toBe('24px')
    expect(find(above, 'div.email-button')!.style.marginTop).toBe('0px')
  })

  it("sets the gap below a box from its last line, not inside it", () => {
    const BOX =
      '<div class="email-box" style="margin:16px 0; padding:12px 14px; border:1px dashed #017151; background-color:#e9f6f1">' +
      '<p>Important</p></div><h2 style="margin:18px 0 8px 0">Please confirm</h2>'
    const editor = new Editor({ extensions: [StarterKit, EmailBox, EmailButton, EmailTextStyle, EmailTextStyles], content: BOX })
    editor.commands.setTextSelection(3)
    // The box's 16px and the heading's 18px meet: 18px.
    expect(gapBelowSelection(editor.state)).toBe('18px')
    editor.commands.setGapBelow('8px')
    expect(gapBelowSelection(editor.state)).toBe('8px')
    const out = editor.getHTML()
    editor.destroy()

    const box = find(out, 'div.email-box')!
    expect(box.style.marginBottom).toBe('8px')
    expect(box.style.borderStyle).toBe('dashed')
    expect(find(out, 'div.email-box p')!.style.marginBottom).toBe('')
    expect(find(out, 'h2')!.style.marginTop).toBe('0px')
  })

  it('knows no gap for text without margins', () => {
    const editor = new Editor({ extensions: [StarterKit, EmailTextStyle, EmailTextStyles], content: '<p>One</p><p>Two</p>' })
    editor.commands.setTextSelection(2)
    expect(gapBelowSelection(editor.state)).toBeNull()
    editor.destroy()
  })
})

describe('textStyleAt', () => {
  const at = (content: string, pos: number, property: string) => {
    const editor = new Editor({ extensions: [StarterKit, EmailBox, EmailButton, EmailTextStyle, EmailTextStyles], content })
    editor.commands.setTextSelection(pos)
    const found = textStyleAt(editor.state, property)
    editor.destroy()
    return found
  }

  it("shows a heading's colour and size, set on the heading", () => {
    const heading = '<h1 style="color:#017151; font-size:26px">Congratulations</h1>'
    expect(at(heading, 3, 'color')).toEqual({ own: null, shown: '#017151' })
    expect(at(heading, 3, 'font-size')).toEqual({ own: null, shown: '26px' })
  })

  it('prefers the colour set on the text itself, then a bold style, then the paragraph', () => {
    const p = '<p style="color:#3d4b43">Plain <strong style="color:#017151">bold</strong> <span style="color:#b3261e">red</span></p>'
    expect(at(p, 3, 'color').shown).toBe('#3d4b43')
    expect(at(p, 10, 'color').shown).toBe('#017151')
    expect(at(p, 16, 'color')).toEqual({ own: '#b3261e', shown: '#b3261e' })
  })

  it('finds nothing where nothing sets one', () => {
    expect(at('<p>Plain</p>', 2, 'color')).toEqual({ own: null, shown: null })
  })
})

describe('marginOf', () => {
  it('reads a top or bottom margin from the shorthand or its own property', () => {
    expect(marginOf('margin:0 0 14px 0', 'bottom')).toBe(14)
    expect(marginOf('margin:14px 0 0 0', 'top')).toBe(14)
    expect(marginOf('margin:16px 0', 'bottom')).toBe(16)
    expect(marginOf('margin:0 0 14px 0; margin-bottom:0', 'bottom')).toBe(0)
    expect(marginOf('color:red', 'top')).toBeNull()
    expect(marginOf('margin:1em 0', 'top')).toBeNull()
  })
})

describe('styleValue', () => {
  it('reads one property out of an inline style', () => {
    expect(styleValue('color: #307054; font-size:12px', 'font-size')).toBe('12px')
    expect(styleValue('color: #307054', 'font-size')).toBeNull()
    expect(styleValue(null, 'color')).toBeNull()
  })
})
