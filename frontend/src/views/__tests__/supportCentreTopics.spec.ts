import { describe, expect, it } from 'vitest'

/**
 * The topic cards on the Support Centre.
 *
 * "Knowledge base" is a naming convention rather than a table: an article is a
 * rich-text resource carrying a label whose name matches one of the three
 * topic cards. That means the whole feature hinges on one string comparison,
 * and getting it wrong fails silently — the cards keep rendering, just without
 * links, and nobody notices the help articles are unreachable.
 *
 * This used to carry a COPY of the matcher, because the original lived inside
 * a <script setup> block and could not be imported. It therefore pinned the
 * rule and not the implementation, and the two were free to drift apart with
 * the suite green. The function now lives in utils/supportTopics.ts and both
 * the page and this file import that one.
 */
import { SUPPORT_TOPICS, labelIdFor } from '@/utils/supportTopics'

const TOPICS = SUPPORT_TOPICS.map((t) => t.title)

describe('matching a support topic to a resource label', () => {
  it('links a topic whose label exists', () => {
    const labels = [{ id: 7, name: 'Account and access' }]
    expect(labelIdFor('Account and access', labels)).toBe('7')
  })

  it('leaves a topic unlinked when nothing matches', () => {
    // The client has not created that label yet. The card must stay plain
    // text rather than link to an empty list.
    expect(labelIdFor('Account and access', [{ id: 7, name: 'Events' }])).toBeUndefined()
  })

  it('ignores case and surrounding space, because a human types these', () => {
    const labels = [{ id: 3, name: '  account and access  ' }]
    expect(labelIdFor('Account and access', labels)).toBe('3')
  })

  it('survives an empty library', () => {
    for (const topic of TOPICS) {
      expect(labelIdFor(topic, [])).toBeUndefined()
    }
  })

  it('does not match on a partial name', () => {
    // "Account" must not pick up "Account and access": the label the client
    // meant is the whole topic, and a prefix match would send someone to the
    // wrong shelf.
    expect(labelIdFor('Account', [{ id: 1, name: 'Account and access' }])).toBeUndefined()
  })

  it('names the same three topics the seeder creates labels for', () => {
    // The load-bearing string comparison, and the one thing no test covered.
    // Three copies of these names have to agree: this list, HELP_LABELS in
    // backend/apps/admin/management/commands/seed_demo.py, and whatever the
    // client has actually created in the resource library. When they disagree
    // the card silently stops being a link — it keeps rendering as plain text
    // and nothing reports it.
    //
    // Only two of the three can be pinned from here. The third is a question
    // for the client, recorded in decisions.md DEC-029 ④.
    expect(TOPICS).toEqual([
      'Account and access',
      'Registration',
      'Certificates and records'
    ])
  })

  it('every card says what it is for', () => {
    for (const topic of SUPPORT_TOPICS) {
      expect(topic.blurb.length).toBeGreaterThan(20)
    }
  })
})
