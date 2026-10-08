import { Extension, Mark, mergeAttributes, type CommandProps } from '@tiptap/core'
import type { Node as ProseMirrorNode } from '@tiptap/pm/model'
import type { EditorState } from '@tiptap/pm/state'
import { cleanEmailStyle } from './emailBlocks'

/**
 * Text colours and sizes for the System Emails editor.
 *
 * The built-in email templates colour and size their text with inline styles
 * (a grey greeting, a green word in a heading, small print). Without these,
 * the editor would drop those styles as it reads a template in, so a saved
 * email lost them. `EmailTextStyles` keeps the style on every kind of text
 * the editor holds; `EmailTextStyle` keeps a styled piece of a line (a
 * `<span>`) and lets admins colour or resize selected text. The server keeps
 * these styles on save (`clean_email_body`).
 */

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    emailTextStyle: {
      /** Colour the selected text; null takes its colour off. */
      setTextColour: (colour: string | null) => ReturnType
      /** Resize the selected text; null takes its size off. */
      setTextSize: (size: string | null) => ReturnType
    }
    emailTextStyles: {
      /** Set the gap below each selected paragraph or heading, e.g. "24px". */
      setGapBelow: (gap: string) => ReturnType
    }
  }
}

export interface TextChoice {
  label: string
  value: string
}

/** The text colours the built-in templates use. */
export const TEXT_COLOURS: readonly TextChoice[] = [
  { label: 'Dark', value: '#1a2e23' },
  { label: 'Body text', value: '#3d4b43' },
  { label: 'Grey', value: '#6d7a72' },
  { label: 'Green', value: '#307054' },
  { label: 'Dark green', value: '#017151' },
  { label: 'Red', value: '#b3261e' }
]

/** The text sizes the built-in templates use. */
export const TEXT_SIZES: readonly TextChoice[] = [
  { label: 'Small', value: '12px' },
  { label: 'Medium', value: '14px' },
  { label: 'Large', value: '18px' },
  { label: 'Extra large', value: '22px' }
]

/** The gaps offered below a paragraph or heading: 14px is the templates'
 *  usual gap between paragraphs, 24px a blank line. */
export const TEXT_GAPS: readonly TextChoice[] = [
  { label: 'No gap', value: '0px' },
  { label: 'Small gap', value: '8px' },
  { label: 'Medium gap', value: '14px' },
  { label: 'Large gap', value: '24px' }
]

/** The value of one property in an inline style, if it's there. */
export function styleValue(style: string | null | undefined, property: string): string | null {
  for (const declaration of (style ?? '').split(';')) {
    const colon = declaration.indexOf(':')
    if (colon < 0) continue
    if (declaration.slice(0, colon).trim().toLowerCase() === property) {
      return declaration.slice(colon + 1).trim() || null
    }
  }
  return null
}

/** The style with one property set to ``value``, or taken off for null. */
function withProperty(style: string | null | undefined, property: string, value: string | null): string {
  const others = (style ?? '')
    .split(';')
    .filter((declaration) => declaration.includes(':') && declaration.split(':')[0].trim().toLowerCase() !== property)
    .join(';')
  return cleanEmailStyle(others, value ? `${property}:${value}` : '')
}

/**
 * A style's top or bottom margin in px, from `margin` or `margin-top` /
 * `margin-bottom`, the later winning; null when it sets none (or not in px).
 */
export function marginOf(style: string | null | undefined, side: 'top' | 'bottom'): number | null {
  let margin: number | null = null
  for (const declaration of (style ?? '').split(';')) {
    const colon = declaration.indexOf(':')
    if (colon < 0) continue
    const property = declaration.slice(0, colon).trim().toLowerCase()
    const value = declaration.slice(colon + 1).trim()
    if (property === 'margin') {
      const parts = value.split(/\s+/)
      margin = toPx(side === 'top' ? parts[0] : parts[2] ?? parts[0])
    } else if (property === `margin-${side}`) {
      margin = toPx(value)
    }
  }
  return margin
}

const toPx = (value: string | undefined): number | null => {
  if (value === undefined) return null
  if (value === '0') return 0
  const px = value.match(/^(-?\d+(?:\.\d+)?)px$/)
  return px ? Number(px[1]) : null
}

/** Blocks a gap is set below: a paragraph, heading or button (a box through
 *  its last paragraph, see gapTargets). */
const GAP_BLOCKS = new Set(['paragraph', 'heading', 'emailButton'])

/** Blocks whose top margin can be cleared, so the gap below the one before is exact. */
const GAP_NEIGHBOURS = new Set([
  'paragraph', 'heading', 'bulletList', 'orderedList', 'blockquote', 'horizontalRule', 'emailBox', 'emailButton'
])

/** Where a block keeps its margins: a button on its wrapper, the rest on themselves. */
const spaceAttribute = (node: ProseMirrorNode) => (node.type.name === 'emailButton' ? 'wrapperStyle' : 'style')

interface Placed {
  pos: number
  node: ProseMirrorNode
}

/** The block after the one at `pos`, if its top margin can be cleared. */
function nextOf(state: EditorState, { pos, node }: Placed): Placed | null {
  const $pos = state.doc.resolve(pos)
  const index = $pos.index()
  const next = index + 1 < $pos.parent.childCount ? $pos.parent.child(index + 1) : null
  return next && GAP_NEIGHBOURS.has(next.type.name) ? { pos: pos + node.nodeSize, node: next } : null
}

/**
 * The blocks in the selection whose gap below can be set, each with the block
 * after it. Text on a box's last line stands for the box: the gap below that
 * line is inside the box, where its padding already sits.
 */
function gapTargets(state: EditorState) {
  const { from, to } = state.selection
  const found = new Map<number, Placed>()
  state.doc.nodesBetween(from, to, (node, pos) => {
    if (!GAP_BLOCKS.has(node.type.name)) return true
    const $pos = state.doc.resolve(pos)
    const inBox = $pos.parent.type.name === 'emailBox' && $pos.index() === $pos.parent.childCount - 1
    if (inBox) found.set($pos.before(), { pos: $pos.before(), node: $pos.parent })
    else found.set(pos, { pos, node })
    return false
  })
  return [...found.values()].map((target) => ({ ...target, after: nextOf(state, target) }))
}

/** Whether the selection has a block whose gap below can be set. */
export const hasGapTarget = (state: EditorState) => gapTargets(state).length > 0

/**
 * The gap below the first selected block, e.g. "24px": the larger of its
 * bottom margin and the top margin of the block after it, as margins meet in
 * an email. Null when neither sets one.
 */
export function gapBelowSelection(state: EditorState): string | null {
  const [first] = gapTargets(state)
  if (!first) return null
  const bottom = marginOf(first.node.attrs[spaceAttribute(first.node)], 'bottom')
  const above = first.after ? marginOf(first.after.node.attrs[spaceAttribute(first.after.node)], 'top') : null
  if (bottom === null && above === null) return null
  return `${Math.max(bottom ?? 0, above ?? 0)}px`
}

const keptStyle = {
  default: null,
  parseHTML: (element: HTMLElement) => cleanEmailStyle(element.getAttribute('style')) || null,
  renderHTML: (attributes: { style?: string | null }) => (attributes.style ? { style: attributes.style } : {})
}

/** A styled piece of a line: `<span style="color:…; font-size:…">`. */
export const EmailTextStyle = Mark.create({
  name: 'emailTextStyle',

  addAttributes() {
    return { style: keptStyle }
  },

  parseHTML() {
    // Only spans that carry a style worth keeping; plain spans stay plain text.
    return [{ tag: 'span', getAttrs: (element) => (cleanEmailStyle((element as HTMLElement).getAttribute('style')) ? {} : false) }]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes), 0]
  },

  addCommands() {
    const restyle = (property: string, value: string | null) => ({ editor, commands }: CommandProps) => {
      const style = withProperty(editor.getAttributes(this.name).style, property, value)
      return style ? commands.setMark(this.name, { style }) : commands.unsetMark(this.name)
    }
    return {
      setTextColour: (colour) => restyle('color', colour),
      setTextSize: (size) => restyle('font-size', size)
    }
  }
})

/**
 * Keeps the inline style on paragraphs, headings, lists, quotes, dividers and
 * on bold, italic, underlined, struck and linked text, so a template's
 * colours, sizes and spacing stay as written.
 */
export const EmailTextStyles = Extension.create({
  name: 'emailTextStyles',

  addGlobalAttributes() {
    return [
      {
        types: [
          'paragraph', 'heading', 'bulletList', 'orderedList', 'listItem', 'blockquote', 'horizontalRule',
          'bold', 'italic', 'underline', 'strike', 'link'
        ],
        attributes: { style: keptStyle }
      }
    ]
  },

  addCommands() {
    return {
      // The gap below a block is its own bottom margin or the top margin of
      // the block after it, whichever is larger. So set the bottom margin and
      // clear that top margin: only the gaps below the selected blocks
      // change, never the gap above them.
      setGapBelow:
        (gap) =>
        ({ state, tr, dispatch }) => {
          const targets = gapTargets(state)
          if (!targets.length) return false
          if (dispatch) {
            const styles = new Map<number, { node: ProseMirrorNode; style: string }>()
            const restyle = (pos: number, node: ProseMirrorNode, property: string, value: string) => {
              const current = styles.get(pos) ?? { node, style: node.attrs[spaceAttribute(node)] ?? '' }
              styles.set(pos, { node, style: withProperty(current.style, property, value) })
            }
            for (const { pos, node, after } of targets) {
              restyle(pos, node, 'margin-bottom', gap)
              if (after) restyle(after.pos, after.node, 'margin-top', '0')
            }
            styles.forEach(({ node, style }, pos) => {
              tr.setNodeMarkup(pos, undefined, { ...node.attrs, [spaceAttribute(node)]: style || null })
            })
          }
          return true
        }
    }
  }
})
