import { describe, expect, it } from 'vitest'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { TableRow } from '@tiptap/extension-table'
import { EmailBox, EmailButton } from '@/components/admin/emailBlocks'
import { EmailTable, EmailTableCell, EmailTableHeader } from '@/components/admin/emailTables'
import { EmailTextStyle, EmailTextStyles } from '@/components/admin/emailTextStyle'

/** An editor as the System Emails editor sets one up. */
const emailEditor = (content: string) =>
  new Editor({
    extensions: [
      StarterKit,
      EmailTable.configure({ resizable: false }),
      TableRow,
      EmailTableHeader,
      EmailTableCell,
      EmailBox,
      EmailButton,
      EmailTextStyle,
      EmailTextStyles
    ],
    content
  })

/** Put the cursor in the text ``text``. */
const cursorIn = (editor: Editor, text: string) => {
  let at = -1
  editor.state.doc.descendants((node, pos) => {
    if (at < 0 && node.isText && node.text?.includes(text)) at = pos + 1
  })
  editor.commands.setTextSelection(at)
}

const cells = (html: string) => {
  const holder = document.createElement('div')
  holder.innerHTML = html
  return Array.from(holder.querySelectorAll<HTMLElement>('td, th'))
}

// An event's details as the RSVP reminder lays them out: no lines, grey labels.
const DETAILS =
  '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">' +
  '<tr><td style="padding:2px 12px 6px 0; color:#6d7a72; font-size:12px; width:80px; vertical-align:top;">Date</td>' +
  '<td style="padding:2px 0 6px 0; color:#1a2e23; font-size:14px;">Friday</td></tr></table>'

describe('email tables', () => {
  it("keep a template table's own look, without lines", () => {
    const editor = emailEditor(DETAILS)
    const html = editor.getHTML()
    editor.destroy()

    const [label, value] = cells(html)
    expect(label.style.border).toBe('')
    expect(label.style.color).toBe('rgb(109, 122, 114)')
    expect(label.style.fontSize).toBe('12px')
    expect(label.style.width).toBe('80px')
    expect(label.style.verticalAlign).toBe('top')
    expect(value.style.padding).toBe('2px 0px 6px')
    expect(html).toMatch(/<table[^>]*style="[^"]*width: 100%/)
  })

  it('draw lines on a new table, and keep them through a save', () => {
    const editor = emailEditor('<p>x</p>')
    editor.commands.insertTable({ rows: 2, cols: 2, withHeaderRow: false })
    const saved = editor.getHTML()
    editor.destroy()
    expect(cells(saved).every((cell) => cell.style.border === '1px solid rgb(209, 213, 219)')).toBe(true)

    // Read back, the lines stay lines: on, and not doubled into the cells' own style.
    const reopened = emailEditor(saved)
    let lines: unknown
    reopened.state.doc.descendants((node) => {
      if (node.type.name === 'table') lines = node.attrs.lines
      if (node.type.name === 'tableCell') expect(node.attrs.style).toBeNull()
    })
    expect(lines).toBe(true)
    reopened.destroy()
  })

  it('switch lines off and on for the whole table', () => {
    const editor = emailEditor('<p>x</p>')
    editor.commands.insertTable({ rows: 2, cols: 2, withHeaderRow: false })
    editor.commands.toggleTableLines()
    expect(cells(editor.getHTML()).every((cell) => cell.style.border === '')).toBe(true)
    editor.commands.toggleTableLines()
    expect(cells(editor.getHTML()).every((cell) => cell.style.border !== '')).toBe(true)
    editor.destroy()
  })

  it('give a row added to a table without lines no lines either', () => {
    const editor = emailEditor(DETAILS)
    cursorIn(editor, 'Friday')
    editor.commands.addRowAfter()
    const added = cells(editor.getHTML()).slice(2)
    editor.destroy()

    expect(added).toHaveLength(2)
    expect(added.every((cell) => cell.style.border === '')).toBe(true)
  })

  it('keep a cell its own padding when lines go off', () => {
    const editor = emailEditor(DETAILS)
    cursorIn(editor, 'Friday')
    editor.commands.toggleTableLines()
    const [label] = cells(editor.getHTML())
    // Lines on: the line border, with the cell's own padding kept over the lines' padding.
    expect(label.style.border).toBe('1px solid rgb(209, 213, 219)')
    expect(label.style.padding).toBe('2px 12px 6px 0px')
    editor.commands.toggleTableLines()
    expect(cells(editor.getHTML())[0].style.border).toBe('')
    editor.destroy()
  })
})
