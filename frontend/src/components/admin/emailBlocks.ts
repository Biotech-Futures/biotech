import { Node } from '@tiptap/core'

/**
 * Box and button blocks for the System Emails editor.
 *
 * The built-in email templates draw boxes and buttons with inline styles
 * (email clients ignore most stylesheets). These blocks read them in, keep
 * their look while the admin edits, and write them back out as
 * `<div class="email-box">` and `<div class="email-button"><a class="cta-link">`
 * with inline styles, which the server keeps on save (`clean_email_body`).
 */

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    emailBox: {
      /** Put the selected lines in a box with this style, or restyle the box they are in. */
      setEmailBox: (style: string) => ReturnType
      /** Take the lines out of their box. */
      unsetEmailBox: () => ReturnType
    }
    emailButton: {
      /** Turn the current line into a button, or change the button's link or style. */
      setEmailButton: (attributes: { href?: string; style?: string }) => ReturnType
    }
  }
}

// Keep in step with EMAIL_STYLE_PROPERTIES in backend/apps/services/system_email.py.
// Text (emailTextStyle.ts) and tables (emailTables.ts) use them too: height
// draws a divider line, border-collapse and width lay out a table.
const STYLE_PROPERTIES = new Set([
  'background-color', 'border', 'border-collapse', 'border-radius', 'color', 'display',
  'font-family', 'font-size', 'font-weight', 'height', 'letter-spacing', 'line-height',
  'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'text-align', 'text-decoration', 'text-transform', 'vertical-align', 'width', 'word-break'
])

export interface EmailLook {
  id: string
  label: string
  style: string
}

/** The boxes the built-in templates draw, offered for new boxes. */
export const BOX_LOOKS: readonly EmailLook[] = [
  {
    id: 'info',
    label: 'Info',
    style: 'margin:16px 0; padding:16px 18px; border:1px solid #d8e1dc; border-radius:8px; background-color:#f4f7f5'
  },
  {
    id: 'highlight',
    label: 'Highlight',
    style: 'margin:16px 0; padding:12px 14px; border:1px dashed #017151; border-radius:10px; background-color:#e9f6f1'
  },
  {
    id: 'warning',
    label: 'Warning',
    style: 'margin:16px 0; padding:16px 18px; border:1px solid #f0c4c1; border-radius:8px; background-color:#fff4f3'
  }
]

/** The buttons the built-in templates draw, offered for new buttons. */
export const BUTTON_LOOKS: readonly EmailLook[] = [
  {
    id: 'dark',
    label: 'Dark green',
    style: 'display:inline-block; background-color:#307054; color:#ffffff; text-decoration:none; padding:13px 30px; border-radius:8px; font-weight:700; font-size:15px'
  },
  {
    id: 'light',
    label: 'Light green',
    style: 'display:inline-block; background-color:#C3EBCA; border:1px solid #007253; color:#007253; text-decoration:none; padding:14px 28px; border-radius:6px; font-weight:700; font-size:16px'
  },
  {
    id: 'finalist',
    label: 'Finalist green',
    style: 'display:inline-block; background-color:#017151; color:#ffffff; text-decoration:none; padding:12px 18px; border-radius:10px; font-weight:700; font-size:16px; text-align:center'
  }
]

/** Used when a box or button's own style can't be read. */
export const BOX_STYLE = BOX_LOOKS[1].style
export const BUTTON_STYLE = BUTTON_LOOKS[2].style
/** The space around a button unless the gap tool sets another. */
export const BUTTON_SPACE = 'margin:20px 0'

/** Just the margins of a style: "margin:20px 0; margin-bottom:0". */
export const marginsOf = (style: string) =>
  cleanEmailStyle(
    style
      .split(';')
      .filter((declaration) => /^\s*margin(-top|-bottom|-left|-right)?\s*:/i.test(declaration))
      .join(';')
  )

/** "#017151" and "rgb(1, 113, 81)" both become "1,113,81". */
export function colourKey(value: string): string {
  const colour = value.trim().toLowerCase()
  const hex = colour.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/)
  if (hex) {
    const digits = hex[1].length === 3 ? [...hex[1]].map((d) => d + d).join('') : hex[1]
    return [0, 2, 4].map((at) => parseInt(digits.slice(at, at + 2), 16)).join(',')
  }
  const rgb = colour.match(/^rgba?\(([^)]*)\)$/)
  if (rgb) return rgb[1].split(',').slice(0, 3).map((part) => parseInt(part, 10)).join(',')
  return colour
}

const fillOf = (style: string) => {
  const match = style.match(/(?:^|;)\s*background-color\s*:\s*([^;]+)/i)
  return match ? colourKey(match[1]) : ''
}

/** Which look a box or button has, going by its fill colour. */
export function lookOf(looks: readonly EmailLook[], style: string): EmailLook | undefined {
  const fill = fillOf(style)
  return fill ? looks.find((look) => fillOf(look.style) === fill) : undefined
}

/** Placeholders that hold a link, e.g. `registration_url` or `magic_link`. */
export const isLinkPlaceholder = (name: string) => /_(url|link)$/.test(name)

/** Just the colours of a look, for a small sample in a menu. */
export const swatchOf = (look: EmailLook) =>
  look.style
    .split(';')
    .filter((part) => /^\s*(background-color|border)\s*:/.test(part))
    .join(';')

const PLAIN_COLOUR = /^(#[0-9a-f]{3,8}|[a-z]+|rgba?\([\d\s.,%]+\))$/i

/**
 * Merge inline styles, later ones winning, keeping only the properties the
 * server allows. Templates write `background:#hex`, kept as `background-color`
 * when it is a plain colour.
 */
export function cleanEmailStyle(...styles: (string | null | undefined)[]): string {
  const kept = new Map<string, string>()
  for (const style of styles) {
    for (const declaration of (style ?? '').split(';')) {
      const colon = declaration.indexOf(':')
      if (colon < 0) continue
      let property = declaration.slice(0, colon).trim().toLowerCase()
      const value = declaration.slice(colon + 1).trim()
      if (!value) continue
      if (property === 'background') {
        if (!PLAIN_COLOUR.test(value)) continue
        property = 'background-color'
      }
      if (STYLE_PROPERTIES.has(property)) kept.set(property, value)
    }
  }
  return [...kept].map(([property, value]) => `${property}:${value}`).join('; ')
}

const styleOf = (element: Element | null | undefined) => element?.getAttribute('style') ?? ''

/** A style that draws something: a background or a border. */
const drawsBox = (style: string) => /(^|;)\s*(background(-color)?|border)\s*:/i.test(style)

const clean = (text: string | null | undefined) => (text ?? '').replace(/\s+/g, ' ').trim()

/**
 * The link of a wrapper that holds nothing but a template button, e.g. main's
 * `<table><tr><td><a class="cta-link">` or the finalist email's
 * `<div><a class="cta-link">`.
 */
function templateButtonLink(wrapper: HTMLElement): HTMLAnchorElement | null {
  const links = wrapper.querySelectorAll<HTMLAnchorElement>('a.cta-link')
  if (links.length !== 1) return null
  return clean(wrapper.textContent) === clean(links[0].textContent) ? links[0] : null
}

/** Whether the editor keeps a `<div>` as a box or a button (any other div's
 *  layout is lost, its text read as plain paragraphs). */
export function keptAsBlock(div: HTMLElement): boolean {
  return (
    div.classList.contains('email-box') ||
    div.classList.contains('email-button') ||
    drawsBox(styleOf(div)) ||
    !!templateButtonLink(div)
  )
}

function buttonAttributes(wrapper: HTMLElement, link: HTMLAnchorElement | null) {
  if (!link) return false
  // Main's buttons paint their colour on the cell around the link.
  const cell = link.closest('td')
  const cellFill = cell && wrapper.contains(cell)
    ? cleanEmailStyle(styleOf(cell)).split('; ').filter((part) => part.startsWith('background-color:'))
    : []
  const centred =
    /text-align\s*:\s*center/i.test(styleOf(wrapper)) ||
    (wrapper.getAttribute('width') === '100%' && cell?.getAttribute('align') === 'center')
  return {
    href: link.getAttribute('href') ?? '',
    style: cleanEmailStyle(cellFill.join(';'), styleOf(link)) || BUTTON_STYLE,
    align: centred ? 'center' : 'left'
  }
}

/** The one cell of a table used as a card (a background or border on the table). */
function cardCell(table: HTMLElement): HTMLElement | null {
  if (!drawsBox(styleOf(table)) || table.querySelector('a.cta-link')) return null
  const rows = table.querySelectorAll(':scope > tbody > tr, :scope > tr')
  if (rows.length !== 1) return null
  const cells = rows[0].querySelectorAll<HTMLElement>(':scope > td')
  return cells.length === 1 ? cells[0] : null
}

// Attributes come only from the parse rules below: TipTap would otherwise
// read `style` straight off the wrapper and skip the cleaning.
const ruleOnly = { parseHTML: () => null, renderHTML: () => ({}) }

export const EmailBox = Node.create({
  name: 'emailBox',
  group: 'block',
  content: 'block+',
  defining: true,

  addAttributes() {
    return { style: { default: BOX_STYLE, ...ruleOnly } }
  },

  parseHTML() {
    return [
      {
        tag: 'div',
        priority: 100,
        getAttrs: (element) => {
          const div = element as HTMLElement
          const ours = div.classList.contains('email-box')
          if (!ours && (!drawsBox(styleOf(div)) || templateButtonLink(div))) return false
          return { style: cleanEmailStyle(styleOf(div)) || BOX_STYLE }
        }
      },
      {
        tag: 'table',
        priority: 100,
        contentElement: (table) => cardCell(table as HTMLElement) as HTMLElement,
        getAttrs: (element) => {
          const cell = cardCell(element as HTMLElement)
          // A box needs the card's look, not the table's layout.
          const look = cleanEmailStyle(styleOf(element as HTMLElement), styleOf(cell))
            .split('; ')
            .filter((declaration) => !/^(border-collapse|width|vertical-align):/.test(declaration))
            .join('; ')
          return cell ? { style: look } : false
        }
      }
    ]
  },

  renderHTML({ node }) {
    return ['div', { class: 'email-box', style: node.attrs.style || BOX_STYLE }, 0]
  },

  addCommands() {
    return {
      setEmailBox:
        (style) =>
        ({ editor, commands }) =>
          editor.isActive(this.name)
            ? commands.updateAttributes(this.name, { style })
            : commands.wrapIn(this.name, { style }),
      unsetEmailBox:
        () =>
        ({ commands }) =>
          commands.lift(this.name)
    }
  }
})

export const EmailButton = Node.create({
  name: 'emailButton',
  group: 'block',
  content: 'text*',
  marks: '',
  defining: true,

  addAttributes() {
    return {
      href: { default: '', ...ruleOnly },
      style: { default: BUTTON_STYLE, ...ruleOnly },
      align: { default: 'left', ...ruleOnly },
      // The space around the button (its wrapper's margins), set by the gap tool.
      wrapperStyle: { default: BUTTON_SPACE, ...ruleOnly }
    }
  },

  parseHTML() {
    return [
      {
        tag: 'div.email-button',
        priority: 110,
        contentElement: 'a',
        getAttrs: (element) => {
          const wrapper = element as HTMLElement
          const attributes = buttonAttributes(wrapper, wrapper.querySelector('a'))
          return attributes && { ...attributes, wrapperStyle: marginsOf(styleOf(wrapper)) || BUTTON_SPACE }
        }
      },
      ...(['table', 'div'] as const).map((tag) => ({
        tag,
        priority: 110,
        contentElement: 'a.cta-link',
        getAttrs: (element: HTMLElement) => buttonAttributes(element, templateButtonLink(element))
      }))
    ]
  },

  renderHTML({ node }) {
    const space = node.attrs.wrapperStyle || BUTTON_SPACE
    return [
      'div',
      { class: 'email-button', style: `${space}; text-align:${node.attrs.align === 'center' ? 'center' : 'left'}` },
      ['a', { class: 'cta-link', href: node.attrs.href, style: node.attrs.style || BUTTON_STYLE }, 0]
    ]
  },

  addCommands() {
    return {
      setEmailButton:
        (attributes) =>
        ({ editor, commands }) =>
          editor.isActive(this.name)
            ? commands.updateAttributes(this.name, attributes)
            : commands.setNode(this.name, attributes)
    }
  }
})
