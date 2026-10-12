import { findParentNode } from '@tiptap/core'
import { Table, TableCell, TableHeader } from '@tiptap/extension-table'
import type { Node as ProseMirrorNode } from '@tiptap/pm/model'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { cleanEmailStyle } from './emailBlocks'
import { keptClass, styleValue, withProperty } from './emailTextStyle'

/**
 * Tables for the System Emails editor, with or without lines.
 *
 * Email clients ignore most stylesheets, so a table's lines are inline
 * borders on every cell. A table you add starts with lines; a template's
 * table (e.g. an event's "Date / Time / Location" details) starts without,
 * keeping its own look: its cells' padding, colours and sizes. "Lines" in the
 * table bar switches them for the whole table. The server keeps both on save.
 */

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    emailTableLines: {
      /** Draw or take away the lines of the table the cursor is in. */
      toggleTableLines: () => ReturnType
    }
  }
}

/** A table's lines: a thin border and some padding on each cell. */
export const LINE_CELL_STYLE = 'border: 1px solid #d1d5db; padding: 6px 10px'

/** The line border as written, or as the browser rewrites it. */
const LINE_BORDER = /^1px solid (#d1d5db|rgb\(\s*209,\s*213,\s*219\s*\))$/i

const styleOf = (element: Element) => element.getAttribute('style') ?? ''

/** Whether a cell carries the lines this editor draws. */
const hasLineBorder = (cell: Element) => LINE_BORDER.test(styleValue(styleOf(cell), 'border') ?? '')

/** A cell's own style: what it carries apart from the lines. */
function ownCellStyle(cell: HTMLElement): string {
  let style = cleanEmailStyle(styleOf(cell))
  if (hasLineBorder(cell)) {
    style = withProperty(style, 'border', null)
    if (styleValue(style, 'padding') === '6px 10px') style = withProperty(style, 'padding', null)
  }
  return style
}

/** A table's own style, its `width` attribute included ("100%" is how templates span the email). */
function ownTableStyle(table: HTMLElement): string {
  const width = table.getAttribute('width')
  const fromAttribute = width ? `width:${/^\d+$/.test(width) ? `${width}px` : width}` : ''
  return cleanEmailStyle(fromAttribute, styleOf(table))
}

/** The cells of a table's own rows, not of a table inside it. */
const ownCells = (table: HTMLTableElement) => Array.from(table.rows).flatMap((row) => Array.from(row.cells))

const cellAttributes = {
  class: keptClass,
  lines: {
    default: true,
    parseHTML: (element: HTMLElement) => hasLineBorder(element),
    renderHTML: () => ({})
  },
  style: {
    default: null,
    parseHTML: (element: HTMLElement) => ownCellStyle(element) || null,
    renderHTML: (attributes: { lines?: boolean; style?: string | null }) => {
      const style = attributes.lines ? cleanEmailStyle(LINE_CELL_STYLE, attributes.style) : attributes.style
      return style ? { style } : {}
    }
  }
}

export const EmailTableCell = TableCell.extend({
  addAttributes() {
    return { ...this.parent?.(), ...cellAttributes }
  }
})

export const EmailTableHeader = TableHeader.extend({
  addAttributes() {
    return { ...this.parent?.(), ...cellAttributes }
  }
})

const syncKey = new PluginKey('emailTableLines')

export const EmailTable = Table.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      class: keptClass,
      // New tables start with lines; a template's table has none.
      lines: {
        default: true,
        parseHTML: (element: HTMLElement) => ownCells(element as HTMLTableElement).some(hasLineBorder),
        renderHTML: () => ({})
      },
      style: {
        default: null,
        parseHTML: (element: HTMLElement) => ownTableStyle(element) || null,
        // Always collapsed, so cells sit edge to edge as `cellspacing="0"` had them.
        renderHTML: (attributes: { style?: string | null }) => ({
          style: cleanEmailStyle('border-collapse: collapse', attributes.style)
        })
      }
    }
  },

  addCommands() {
    return {
      ...this.parent?.(),
      toggleTableLines:
        () =>
        ({ state, tr, dispatch }) => {
          const table = findParentNode((node) => node.type.name === this.name)(state.selection)
          if (!table) return false
          if (dispatch) tr.setNodeMarkup(table.pos, undefined, { ...table.node.attrs, lines: !table.node.attrs.lines })
          return true
        }
    }
  },

  addProseMirrorPlugins() {
    const tableName = this.name
    return [
      ...(this.parent?.() ?? []),
      // Every cell draws its table's lines or not: after a switch, and for
      // rows or columns added later (they start with the default).
      new Plugin({
        key: syncKey,
        appendTransaction: (transactions, _old, state) => {
          if (!transactions.some((transaction) => transaction.docChanged)) return null
          const tr = state.tr
          state.doc.descendants((node, pos) => {
            if (node.type.name !== tableName) return true
            const lines = node.attrs.lines
            node.forEach((row: ProseMirrorNode, rowOffset: number) => {
              row.forEach((cell: ProseMirrorNode, cellOffset: number) => {
                if ('lines' in cell.attrs && cell.attrs.lines !== lines) {
                  // pos + 1 enters the table, + 1 again enters the row.
                  tr.setNodeMarkup(pos + 1 + rowOffset + 1 + cellOffset, undefined, { ...cell.attrs, lines })
                }
              })
            })
            return true
          })
          return tr.docChanged ? tr : null
        }
      })
    ]
  }
})
