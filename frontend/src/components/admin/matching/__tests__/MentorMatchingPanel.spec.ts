import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import MentorMatchingPanel from '@/components/admin/matching/MentorMatchingPanel.vue'

/**
 * Integration coverage for the Mentor Matching tab: panel, composable, Zod
 * parsing and adminAPI are all real — only `fetch` is faked.
 */

const unmatchedGroups = [
  {
    groupId: 11,
    groupName: 'BTF11',
    countryName: 'Australia',
    studentInterests: ['Immunology'],
    studentCount: 2,
    students: [{ name: 'Tara Petrov', hasLoggedIn: true, interests: ['Immunology'] }]
  }
]

const mentorList = [
  {
    mentorId: 4,
    name: 'Felix Reyes',
    countryName: 'Australia',
    institution: 'University of Melbourne',
    interests: ['Immunology'],
    maxGroupCount: 3,
    currentAssignedCount: 1,
    remainingCapacity: 2
  },
  {
    mentorId: 9,
    name: 'Oscar Nguyen',
    countryName: 'Australia',
    institution: 'QIMR Berghofer',
    interests: ['Genetics'],
    maxGroupCount: 2,
    currentAssignedCount: 2,
    remainingCapacity: 0
  }
]

const recommendations = [
  {
    group: {
      groupId: 11,
      groupName: 'BTF11',
      countryName: 'Australia',
      studentInterests: ['Immunology'],
      studentCount: 2
    },
    recommendedMentor: {
      mentorId: 4,
      name: 'Felix Reyes',
      countryName: 'Australia',
      institution: 'University of Melbourne',
      interests: ['Immunology'],
      remainingCapacity: 2
    },
    reason: 'Country match: Australia. Shared interests: Immunology.',
    score: 121,
    scoreBreakdown: {
      baseScore: 100,
      countryPenalty: 0,
      interestBonus: 15,
      timezonePenalty: 0,
      capacityBonus: 6,
      objectiveScore: 121
    }
  }
]

const jsonResponse = (payload: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { 'Content-Type': 'application/json' }
    })
  )

const fetchMock = (options: { recommendStatus?: number } = {}) =>
  vi.fn().mockImplementation((url: string) => {
    const target = String(url)
    if (target.includes('/services/csrf/')) return jsonResponse({ csrfToken: 'csrf-test' })
    if (target.includes('/mentor-match/recommend/')) {
      if (options.recommendStatus && options.recommendStatus >= 400) {
        return jsonResponse({ msg: 'Server error' }, options.recommendStatus)
      }
      return jsonResponse({ msg: 'ok', data: recommendations })
    }
    if (target.includes('/mentor-match/confirm/')) {
      return jsonResponse({ msg: 'ok', data: { confirmedCount: 1 } })
    }
    if (target.includes('/mentor-match/groups/')) {
      return jsonResponse({ msg: 'ok', data: unmatchedGroups })
    }
    if (target.includes('/mentor-match/mentors/')) {
      return jsonResponse({ msg: 'ok', data: mentorList })
    }
    return jsonResponse({})
  })

const buttonByText = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().trim().startsWith(label))

const runMatch = async (wrapper: VueWrapper) => {
  await buttonByText(wrapper, 'Run match')!.trigger('click')
  await flushPromises()
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('MentorMatchingPanel', () => {
  it('loads the reference tables on mount', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()

    expect(wrapper.text()).toContain('Unmatched Groups')
    expect(wrapper.text()).toContain('BTF11')
    expect(wrapper.text()).toContain('Mentors')
    expect(wrapper.text()).toContain('Felix Reyes')
  })

  it('does not run the matcher on mount', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()

    const calls = fetch.mock.calls.filter((call) =>
      String(call[0]).includes('/mentor-match/recommend/')
    )
    expect(calls).toHaveLength(0)
    expect(wrapper.text()).toContain('to generate recommendations')
  })

  it('hides mentors at capacity until the toggle is on', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()

    // Oscar Nguyen has remainingCapacity 0.
    expect(wrapper.text()).not.toContain('Oscar Nguyen')

    await wrapper.find('input[type="checkbox"]').setValue(true)
    expect(wrapper.text()).toContain('Oscar Nguyen')
  })

  it('replaces the reference tables with the recommendations table on run', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)

    expect(wrapper.text()).not.toContain('Unmatched Groups')
    expect(wrapper.text()).toContain('Recommended Mentor')
    expect(wrapper.text()).toContain('Capacity left')
    expect(wrapper.text()).toContain('Felix Reyes')
  })

  it('requires a selection before confirming', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)

    // Nothing is pre-ticked: confirming writes live assignments, so the admin
    // opts in per row.
    expect(buttonByText(wrapper, 'Confirm selected (0)')).toBeDefined()
    expect(buttonByText(wrapper, 'Confirm')!.attributes('disabled')).toBeDefined()
  })

  it('posts the selected assignment on confirm', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)

    // Row checkboxes live in the table body; the first is select-all.
    const rowCheckbox = wrapper.findAll('tbody input[type="checkbox"]')[0]
    await rowCheckbox.setValue(true)
    await buttonByText(wrapper, 'Confirm')!.trigger('click')
    await flushPromises()

    const confirmCall = fetch.mock.calls.find((call) =>
      String(call[0]).includes('/mentor-match/confirm/')
    )
    expect(confirmCall).toBeDefined()
    const body = JSON.parse((confirmCall![1] as RequestInit).body as string)
    expect(body.assignments).toEqual([{ groupId: 11, mentorUserId: 4 }])
  })

  it('clears the board when the matching mode changes', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)
    expect(wrapper.text()).toContain('Capacity left')

    // Results are mode-specific; leaving stale ones on screen would
    // misrepresent what is about to be confirmed.
    await buttonByText(wrapper, 'Strict')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Capacity left')
    expect(wrapper.text()).toContain('to generate recommendations')
  })

  it('shows the score breakdown when a row is expanded', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)

    await wrapper.find('.mentor-matching__expand-btn').trigger('click')

    expect(wrapper.text()).toContain('Interest overlap')
    expect(wrapper.text()).toContain('Capacity bonus')
    // Zero contributions are omitted so only what moved the score is listed.
    expect(wrapper.text()).not.toContain('Country mismatch')
    expect(wrapper.text()).toContain('Shared interests: Immunology.')
  })

  it('surfaces a failed run with a retry action', async () => {
    vi.stubGlobal('fetch', fetchMock({ recommendStatus: 500 }))
    wrapper = mount(MentorMatchingPanel)
    await flushPromises()
    await runMatch(wrapper)

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(buttonByText(wrapper, 'Retry')).toBeDefined()
    expect(wrapper.text()).not.toContain('Capacity left')
  })
})
