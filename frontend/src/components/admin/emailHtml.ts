import { keptAsBlock } from './emailBlocks'

/**
 * The System Emails editor's HTML view: what the visual view would drop from
 * some HTML, so switching to it can warn first, and a readable layout for the
 * editor's own HTML.
 */

/** Tags the visual view reads (it keeps their text, styles and class names). */
const VISUAL_TAGS = new Set([
  'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'del',
  'a', 'ul', 'ol', 'li', 'blockquote', 'hr', 'span', 'code', 'pre', 'img',
  'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'colgroup', 'col', 'div'
])

/** What the visual view would drop from ``html``, as a reader would put it; empty when nothing. */
export function visualLosses(html: string): string[] {
  const losses: string[] = []
  if (/<!--/.test(html)) losses.push("Outlook's button code and other HTML comments")
  const holder = document.createElement('template')
  holder.innerHTML = html
  const unknown = new Set<string>()
  let layoutDivs = false
  holder.content.querySelectorAll<HTMLElement>('*').forEach((element) => {
    const tag = element.tagName.toLowerCase()
    if (!VISUAL_TAGS.has(tag)) unknown.add(tag)
    else if (tag === 'div' && !keptAsBlock(element)) layoutDivs = true
  })
  if (layoutDivs) losses.push('layouts made with <div>')
  if (unknown.size) losses.push(`the tags ${[...unknown].map((tag) => `<${tag}>`).join(', ')}`)
  return losses
}

/** One block per line: the editor writes its HTML on a single line. Only
 *  after blocks, so no space appears between words or inline tags. */
export const formatHtml = (html: string) =>
  html.replace(/(<\/(?:p|h[1-6]|li|ul|ol|div|table|tbody|thead|tr|blockquote|pre)>|<hr[^>]*>)(?=<)/g, '$1\n')
