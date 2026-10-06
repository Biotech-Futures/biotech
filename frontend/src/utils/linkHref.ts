/**
 * A link as typed into the editor's link dialog, or null if it can't be one.
 *
 * Accepts a placeholder such as `{{ registration_url }}` (maybe followed by a
 * path), a web address, or an email address; a bare `biotechfutures.org` gets
 * https:// and an email address gets mailto:. Site paths like `/events` are
 * only accepted with `allowRelative`: they work on the platform's own pages,
 * but not in an email.
 */
export function linkHref(value: string, options: { allowRelative?: boolean } = {}): string | null {
  const link = value.trim()
  if (/^\{\{\s*\w+\s*\}\}\S*$/.test(link)) return link
  if (/^(https?:\/\/|mailto:)\S+$/i.test(link)) return link
  if (options.allowRelative && /^\/\S*$/.test(link)) return link
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(link)) return `mailto:${link}`
  if (/^[^\s/@:]+\.[^\s/@:]+(\/\S*)?$/.test(link)) return `https://${link}`
  return null
}
