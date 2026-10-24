/**
 * Matching a Support Centre topic card to the resource label that holds its
 * articles.
 *
 * "Knowledge base" is a naming convention rather than a table. The platform
 * already has rich-text resources, an editor the client can use and
 * role-based visibility, so an article is a resource carrying a label whose
 * name matches one of the client's three topics. The client adds an article
 * by writing a resource and labelling it; nothing here changes when they do.
 *
 * The whole feature therefore hinges on one string comparison, and getting it
 * wrong fails silently: the cards keep rendering, just without links, and
 * nobody notices the help articles are unreachable.
 *
 * It lives in this module rather than inside the page's `<script setup>` block
 * for one reason: a `<script setup>` binding cannot be imported, so the test
 * that covered it had copied the function into the test file. That test
 * pinned the rule and not the implementation, and the two were free to drift
 * apart with the suite green.
 */
/**
 * The three cards, and the exact strings the whole feature hinges on.
 *
 * They live here rather than in the page's `<script setup>` block for the same
 * reason the matcher does: a `<script setup>` binding cannot be imported, so
 * anything defined there can only be tested by a copy, and a copy is free to
 * drift from what ships while the suite stays green.
 *
 * Three cards and not one per category. These are the topics people look up
 * for themselves; the eight-item dropdown on the form is what they pick once
 * they have decided to ask a person. Eight cards would mean the client has to
 * author eight labelled collections before any card became a link.
 *
 * 🔴 These strings must match, exactly:
 *   - HELP_LABELS in backend/apps/admin/management/commands/seed_demo.py
 *   - whatever resource labels the client has actually created
 * The match is a case-insensitive whole-string compare with no fallback, so
 * getting it wrong fails silently: the card keeps rendering, just as plain
 * text, and nobody is told the help articles are unreachable.
 */
export const SUPPORT_TOPICS = [
  {
    title: 'Account and access',
    blurb: 'Login issues, password reset, and account settings.'
  },
  {
    title: 'Registration',
    blurb: 'Signing up, guardian consent, and joining a group.'
  },
  {
    title: 'Certificates and records',
    blurb: 'Certificate requests, name updates, and transcripts.'
  }
] as const

export interface ResourceLabelLike {
  id: number
  name: string
}

export function labelIdFor(
  topic: string,
  labels: ResourceLabelLike[]
): string | undefined {
  const match = labels.find(
    (label) => label.name.trim().toLowerCase() === topic.trim().toLowerCase()
  )
  return match ? String(match.id) : undefined
}
