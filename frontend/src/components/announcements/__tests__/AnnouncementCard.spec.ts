import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import AnnouncementCard from '@/components/announcements/AnnouncementCard.vue'
import type { Announcement } from '@/composables/useAnnouncements'

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: vi.fn() })
}))
// Marking it seen, stood in for.
const { markSeen } = vi.hoisted(() => ({ markSeen: vi.fn() }))
vi.mock('@/composables/useAnnouncements', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/composables/useAnnouncements')>()),
  markAnnouncementSeen: markSeen
}))

const announcement: Announcement = {
  id: 7,
  title: 'Welcome',
  date: '2026-10-01T00:00:00Z',
  author: 'Administrator',
  bodyText: 'A long welcome.',
  bodyHtml: '<p>A long welcome.</p><p>More.</p><p>And more.</p>',
  audience: 'global',
  audienceRoles: [],
  audiences: [],
  isPublic: true,
  groupIds: [],
  images: []
}

const mountCard = (over: Partial<Announcement> = {}) =>
  mount(AnnouncementCard, {
    props: { announcement: { ...announcement, ...over } },
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } }
  })

// The text box as the browser would measure it: ``tall`` px of text in ``shown`` px.
const measured = (el: Element, tall: number, shown: number) => {
  Object.defineProperty(el, 'scrollHeight', { configurable: true, value: tall })
  Object.defineProperty(el, 'clientHeight', { configurable: true, value: shown })
}

describe('AnnouncementCard', () => {
  it('has no View details link', () => {
    expect(mountCard().text()).not.toContain('View details')
  })

  it('shows no chevron when the whole announcement fits', async () => {
    const wrapper = mountCard()
    await flushPromises()
    expect(wrapper.find('.announcement__expand').exists()).toBe(false)
    expect(wrapper.find('.announcement__content--clipped').exists()).toBe(false)
  })

  it('expands to the whole announcement and collapses again', async () => {
    const wrapper = mountCard()
    measured(wrapper.find('.announcement__content').element, 400, 110)
    window.dispatchEvent(new Event('resize'))
    await flushPromises()

    const chevron = wrapper.find('.announcement__expand')
    expect(chevron.attributes('aria-expanded')).toBe('false')
    expect(chevron.attributes('aria-label')).toBe('Show more')
    expect(chevron.find('i').classes()).toContain('fa-chevron-down')
    expect(wrapper.find('.announcement__content').classes()).toContain('announcement__content--clipped')

    await chevron.trigger('click')
    expect(chevron.attributes('aria-expanded')).toBe('true')
    expect(chevron.attributes('aria-label')).toBe('Show less')
    expect(chevron.find('i').classes()).toContain('fa-chevron-up')
    expect(wrapper.find('.announcement').classes()).toContain('announcement--expanded')
    expect(wrapper.find('.announcement__content').classes()).toEqual(
      expect.arrayContaining(['announcement__content--open'])
    )

    await chevron.trigger('click')
    expect(wrapper.find('.announcement').classes()).not.toContain('announcement--expanded')
  })

  it('shows a red New until opened, by expanding it or by its title', async () => {
    markSeen.mockClear()
    let wrapper = mountCard({ isNew: true })
    expect(wrapper.find('.announcement__new').text()).toBe('New')

    measured(wrapper.find('.announcement__content').element, 400, 110)
    window.dispatchEvent(new Event('resize'))
    await flushPromises()
    await wrapper.find('.announcement__expand').trigger('click')
    expect(wrapper.find('.announcement__new').exists()).toBe(false)
    expect(markSeen).toHaveBeenCalledWith(7)
    wrapper.unmount()

    markSeen.mockClear()
    wrapper = mountCard({ isNew: true })
    await wrapper.find('.announcement__title-link').trigger('click')
    expect(wrapper.find('.announcement__new').exists()).toBe(false)
    expect(markSeen).toHaveBeenCalledTimes(1)
  })

  it('shows no New once seen', () => {
    expect(mountCard({ isNew: false }).find('.announcement__new').exists()).toBe(false)
  })

  it('shows every targeted role in the audience badge', () => {
    const wrapper = mountCard({
      audience: 'student,mentor,supervisor',
      audienceRoles: ['student', 'mentor', 'supervisor']
    })
    expect(wrapper.find('.announcement__badge').text()).toBe('Student, Mentor, Supervisor')
  })
})
