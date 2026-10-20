/**
 * Inline styles the rich-text editor keeps (text colour, size, gaps, and the
 * email boxes, buttons and tables), and cleaning a style down to them. Shared
 * by the editor and the pages that show what it wrote, so a colour set in an
 * event or announcement shows there too. No editor code, so pages that only
 * display rich text don't load the editor.
 */

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
