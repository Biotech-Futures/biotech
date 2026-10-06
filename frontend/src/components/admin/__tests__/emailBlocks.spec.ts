import { describe, expect, it } from 'vitest'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { Table, TableCell, TableHeader, TableRow } from '@tiptap/extension-table'
import {
  BOX_LOOKS,
  BUTTON_LOOKS,
  EmailBox,
  EmailButton,
  cleanEmailStyle,
  isLinkPlaceholder,
  lookOf
} from '@/components/admin/emailBlocks'

/**
 * ProseMirror writes styles through `element.style`, which rewrites them
 * (#fff becomes rgb(255, 255, 255)), so expected HTML goes through it too.
 */
const same = (html: string) => {
  const holder = document.createElement('div')
  holder.innerHTML = html
  holder.querySelectorAll<HTMLElement>('[style]').forEach((element) => {
    element.style.cssText = element.getAttribute('style') ?? ''
  })
  return holder.innerHTML
}

/** What the System Emails editor makes of some HTML. */
const edit = (html: string, change?: (editor: Editor) => void) => {
  const editor = new Editor({
    extensions: [StarterKit, Table, TableRow, TableHeader, TableCell, EmailBox, EmailButton],
    content: html
  })
  change?.(editor)
  const out = editor.getHTML()
  editor.destroy()
  return out
}

// Markup as the built-in templates write it.
const FINALIST_BOX = `<div style="margin:16px 0; padding:12px 14px; border:1px dashed #017151; border-radius:10px; background:#e9f6f1; color:#153226;">
  <strong>Important:</strong> The Symposium is in-person only.
</div>`
const FINALIST_BUTTON = `<div style="margin:16px 0;">
  <a class="cta-link" href="{{ registration_url }}" style="display:inline-block; background:#017151; color:#ffffff; padding:12px 18px;">Register for the Symposium</a>
</div>`
const CARD = `<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#fff4f3; border:1px solid #f0c4c1; border-radius:8px; border-collapse:separate;">
  <tr><td style="padding:16px 18px;">
    <p style="margin:0; color:#b3261e;">Didn't change your password?</p>
    <p style="margin:0;">Contact us.</p>
  </td></tr>
</table>`
const CENTRED_BUTTON = `<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">
  <tr><td align="center" style="padding:28px 0 22px 0;">
    <!--[if mso]><v:roundrect href="{{ magic_link }}"><center>Log in instantly</center></v:roundrect><![endif]-->
    <!--[if !mso]><!-- --><a class="cta-link" href="{{ magic_link }}" style="background:#C3EBCA; border:1px solid #007253; color:#007253; display:inline-block;">Log in instantly</a><!--<![endif]-->
  </td></tr>
</table>`
const CELL_BUTTON = `<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:26px 0 0 0;">
  <tr><td align="center" style="border-radius:8px; background:#307054;">
    <a class="cta-link" href="{{ submission_url }}" style="display:inline-block; padding:13px 30px; color:#ffffff;">View your submission</a>
  </td></tr>
</table>`

const box = (style: string, content: string) =>
  same(`<div class="email-box" style="${style}">${content}</div>`)
const button = (align: string, href: string, style: string, label: string) =>
  same(
    `<div class="email-button" style="margin:20px 0; text-align:${align}">` +
      `<a class="cta-link" href="${href}" style="${style}">${label}</a></div>`
  )

describe('cleanEmailStyle', () => {
  it('keeps allowed properties and turns a plain background into background-color', () => {
    expect(cleanEmailStyle('BACKGROUND:#e9f6f1; position:absolute; Color:#fff;')).toBe(
      'background-color:#e9f6f1; color:#fff'
    )
  })

  it('drops a background that is more than a colour', () => {
    expect(cleanEmailStyle('background:url(https://example.com/x.png); padding:4px')).toBe('padding:4px')
  })

  it('lets later styles win', () => {
    expect(cleanEmailStyle('background-color:#111; color:#222', 'color:#333')).toBe(
      'background-color:#111; color:#333'
    )
  })
})

describe('email boxes', () => {
  it('reads the finalist box with its look', () => {
    expect(edit(FINALIST_BOX)).toBe(
      box(
        'margin:16px 0; padding:12px 14px; border:1px dashed #017151; border-radius:10px; background-color:#e9f6f1; color:#153226',
        '<p><strong>Important:</strong> The Symposium is in-person only.</p>'
      )
    )
  })

  it("reads a card table as a box, with the cell's padding", () => {
    expect(edit(CARD)).toBe(
      box(
        'background-color:#fff4f3; border:1px solid #f0c4c1; border-radius:8px; padding:16px 18px',
        "<p>Didn't change your password?</p><p>Contact us.</p>"
      )
    )
  })

  it('leaves a table without a background or border as a table', () => {
    expect(edit('<table><tr><td>Date</td><td>Friday</td></tr></table>')).toContain('<table')
  })

  it('puts lines in a box of the chosen look, restyles it, and takes them out again', () => {
    const [info, , warning] = BOX_LOOKS
    const boxed = edit('<p>Note</p>', (editor) => editor.commands.setEmailBox(info.style))
    // StarterKit keeps an empty line after a last block that isn't a paragraph.
    expect(boxed).toBe(box(info.style, '<p>Note</p>') + '<p></p>')

    const restyled = edit(boxed, (editor) => editor.chain().setTextSelection(3).setEmailBox(warning.style).run())
    expect(restyled).toBe(box(warning.style, '<p>Note</p>') + '<p></p>')

    expect(edit(boxed, (editor) => editor.chain().setTextSelection(3).unsetEmailBox().run())).toBe(
      '<p>Note</p><p></p>'
    )
  })
})

describe('looks', () => {
  it("names each template box and button's look, whichever way its colour is written", () => {
    const ids = (looks: typeof BOX_LOOKS, styles: string[]) => styles.map((style) => lookOf(looks, style)?.id)
    expect(ids(BOX_LOOKS, ['background:#f4f7f5', 'background-color:#E9F6F1', 'background-color: rgb(255, 244, 243)'].map((s) => cleanEmailStyle(s)))).toEqual(
      ['info', 'highlight', 'warning']
    )
    expect(ids(BUTTON_LOOKS, ['background-color:#307054', 'background-color:rgb(195, 235, 202)', 'background-color:#017151'])).toEqual(
      ['dark', 'light', 'finalist']
    )
    expect(lookOf(BOX_LOOKS, 'background-color:#123456')).toBeUndefined()
    expect(lookOf(BOX_LOOKS, 'padding:4px')).toBeUndefined()
  })
})

describe('email buttons', () => {
  it('reads the finalist button with its link and look', () => {
    expect(edit(FINALIST_BUTTON)).toBe(
      button(
        'left',
        '{{ registration_url }}',
        'display:inline-block; background-color:#017151; color:#ffffff; padding:12px 18px',
        'Register for the Symposium'
      )
    )
  })

  it('reads a centred button and ignores the Outlook-only copy', () => {
    expect(edit(CENTRED_BUTTON)).toBe(
      button(
        'center',
        '{{ magic_link }}',
        'background-color:#C3EBCA; border:1px solid #007253; color:#007253; display:inline-block',
        'Log in instantly'
      )
    )
  })

  it('takes the colour from the cell when the link has none', () => {
    expect(edit(CELL_BUTTON)).toBe(
      button(
        'left',
        '{{ submission_url }}',
        'background-color:#307054; display:inline-block; padding:13px 30px; color:#ffffff',
        'View your submission'
      )
    )
  })

  it('does not read a wrapper holding more than the button as a button', () => {
    const html = edit(`<div style="margin:0"><p>Hello</p>${FINALIST_BUTTON}</div>`)
    expect(html).toContain('<p>Hello</p>')
    expect(html).toContain('class="email-button"')
  })

  it('turns a line into a button of the chosen look, dropping its formatting', () => {
    const [dark, light] = BUTTON_LOOKS
    const html = edit('<p>Open <strong>it</strong></p>', (editor) =>
      editor.commands.setEmailButton({ href: '{{ platform_url }}', style: dark.style })
    )
    expect(html).toBe(button('left', '{{ platform_url }}', dark.style, 'Open it') + '<p></p>')

    // Changing the look keeps the link, and changing the link keeps the look.
    const restyled = edit(html, (editor) =>
      editor.chain().setTextSelection(2).setEmailButton({ style: light.style }).setEmailButton({ href: '{{ other_url }}' }).run()
    )
    expect(restyled).toBe(button('left', '{{ other_url }}', light.style, 'Open it') + '<p></p>')
  })
})

it('knows which placeholders hold links', () => {
  const names = ['registration_url', 'magic_link', 'group_name', 'symposium_date', 'event_join_link']
  expect(names.filter(isLinkPlaceholder)).toEqual(['registration_url', 'magic_link', 'event_join_link'])
})

it('reads its own output back unchanged', () => {
  const once = edit(FINALIST_BOX + FINALIST_BUTTON + CARD + CENTRED_BUTTON + CELL_BUTTON)
  expect(edit(once)).toBe(once)
})
