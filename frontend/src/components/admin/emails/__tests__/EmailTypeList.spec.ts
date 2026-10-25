import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmailTypeList from '../EmailTypeList.vue'
import type { SystemEmailTemplate } from '@/utils/systemEmail'

const email = (key: string, name: string) =>
  ({ key, name, description: '' }) as unknown as SystemEmailTemplate

describe('EmailTypeList', () => {
  // The ticket system's six joined System Emails on 20 and 22 October, in
  // the registry's order: after the results, before the credits alert,
  // which has no group and shows under Other.
  it('puts the six ticket emails under a heading of their own', () => {
    const wrapper = mount(EmailTypeList, {
      props: {
        selectedKey: null,
        templates: [
          email('results_supervisor', 'Results (to supervisors)'),
          email('ticket_submitted', 'Enquiry received (to the requester)'),
          email('ticket_reply', 'Reply to an enquiry (to the requester)'),
          email('ticket_resolved', 'Enquiry resolved (to the requester)'),
          email('ticket_new_for_support', 'New enquiry (to the support inbox)'),
          email('ticket_flagged_for_support', 'Flagged chat message (to the support inbox)'),
          email('ticket_digest', 'Open enquiries summary (to the support inbox)'),
          email('email_credits_low', 'Email verification credits low')
        ]
      }
    })

    expect(wrapper.findAll('[data-test="email-group"]').map((heading) => heading.text())).toEqual([
      'Results',
      'Support enquiries',
      'Other'
    ])
  })
})
