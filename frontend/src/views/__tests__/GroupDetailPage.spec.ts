import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import GroupDetailPage from '../GroupDetailPage.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/groups/:id', name: 'group-detail', component: GroupDetailPage },
    { path: '/groups/:id/plan', name: 'group-plan', component: GroupDetailPage },
  ],
})

describe('GroupDetailPage mutual interests in members modal', () => {
  let wrapper: VueWrapper | null = null

  beforeEach(async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 20, role: 'mentor', email: 'mentor@example.com' } as any
    await router.push('/groups/1')
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
      wrapper = null
    }
    vi.restoreAllMocks()
  })

  const mountPage = async (membersPayload: unknown[] = []) => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation((url: string) => {
        const u = String(url)
        if (u.includes('/services/csrf/')) {
          return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf' }), { status: 200 }))
        }
        if (u.includes('/groups/groups/1/')) {
          return Promise.resolve(
            new Response(
              JSON.stringify({ id: 1, group_name: 'BTF01', created_at: '2026-01-01T00:00:00Z' }),
              { status: 200 },
            ),
          )
        }
        if (u.includes('/groups/group-members/by-group/1/')) {
          return Promise.resolve(new Response(JSON.stringify(membersPayload), { status: 200 }))
        }
        if (u.includes('/tasks/')) {
          return Promise.resolve(new Response(JSON.stringify({ results: [] }), { status: 200 }))
        }
        if (u.includes('/resources/')) {
          return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
        }
        return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
      }),
    )

    wrapper = mount(GroupDetailPage, {
      global: {
        plugins: [router],
        stubs: {
          GroupSubmissionSection: true,
          AppDatePicker: true,
        },
      },
    })
    await flushPromises()
  }

  it('treats the Plan route as a group section, like Submission', async () => {
    await mountPage()
    expect(wrapper!.find('.group-detail').classes()).not.toContain('group-detail--section')

    await router.push('/groups/1/plan')
    await flushPromises()
    expect(wrapper!.find('.group-detail').classes()).toContain('group-detail--section')
  })

  it('renders mutual interests under "Mutual Interests" heading in members modal when 2 or more members share interests', async () => {
    const members = [
      {
        id: 1,
        group: 1,
        user: 10,
        user_name: 'Alice',
        membership_role: 'student',
        interests: ['Bioinformatics', 'Genetics'],
      },
      {
        id: 2,
        group: 1,
        user: 11,
        user_name: 'Bob',
        membership_role: 'student',
        interests: ['Bioinformatics', 'Robotics'],
      },
      {
        id: 3,
        group: 1,
        user: 20,
        user_name: 'Dr. Mentor',
        membership_role: 'mentor',
        interests: ['Bioinformatics', 'Genetics'],
      },
    ]

    await mountPage(members)

    // Open members modal
    const membersBtn = wrapper!.find('.group-members-btn')
    expect(membersBtn.exists()).toBe(true)
    await membersBtn.trigger('click')
    await flushPromises()

    const modal = wrapper!.find('.group-members-dialog')
    expect(modal.exists()).toBe(true)

    // Heading
    const interestsSection = modal.find('.group-members-dialog-interests')
    expect(interestsSection.exists()).toBe(true)
    expect(interestsSection.find('h4').text()).toBe('Mutual Interests')

    // Interest tags
    const tags = interestsSection.findAll('.group-detail__interest-tag')
    expect(tags.length).toBe(2)
    // Bioinformatics shared by 3 members
    expect(tags[0]!.text()).toContain('Bioinformatics')
    expect(tags[0]!.text()).toContain('(3)')
    // Genetics shared by 2 members
    expect(tags[1]!.text()).toContain('Genetics')
    expect(tags[1]!.text()).toContain('(2)')
    // Robotics shared by only 1 member -> not included
    expect(interestsSection.text()).not.toContain('Robotics')
  })

  it('renders "No mutual areas of interest identified yet." when members do not share interests', async () => {
    const members = [
      {
        id: 1,
        group: 1,
        user: 10,
        user_name: 'Alice',
        membership_role: 'student',
        interests: ['Genetics'],
      },
      {
        id: 2,
        group: 1,
        user: 11,
        user_name: 'Bob',
        membership_role: 'student',
        interests: ['Space & Astrobiology'],
      },
    ]

    await mountPage(members)

    // Open members modal
    const membersBtn = wrapper!.find('.group-members-btn')
    await membersBtn.trigger('click')
    await flushPromises()

    const interestsSection = wrapper!.find('.group-members-dialog-interests')
    expect(interestsSection.exists()).toBe(true)
    expect(interestsSection.text()).toContain('Mutual Interests')
    expect(interestsSection.text()).toContain('No mutual areas of interest identified yet.')
  })
})
