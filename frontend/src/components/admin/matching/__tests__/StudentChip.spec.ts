import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import StudentChip from '@/components/admin/matching/StudentChip.vue'
import type { MatchStudent, RecommendedStudent } from '@/utils/adminMatching'

const student: MatchStudent = {
  id: 12,
  name: 'Nadia Haddad',
  country: 'United States',
  yearLevel: 12,
  interests: ['Synthetic Biology', 'Biomedical Engineering']
}

const entry: RecommendedStudent = {
  student,
  reason: "Shares interest 'synthetic biology' with the group.",
  score: 88,
  scoreBreakdown: {
    baseScore: 100,
    yearPenalty: 0,
    countryPenalty: 12,
    timezonePenalty: 0,
    sizeBonus: 3,
    totalPenalty: 12,
    objectiveScore: 91
  }
}

afterEach(() => {
  document.body.querySelectorAll('.student-chip-card').forEach((node) => node.remove())
})

describe('StudentChip', () => {
  // vuedraggable requires each #item to render a single root element. A
  // top-level <Teleport> sibling turns this into a fragment, which stops
  // dragging with no error at all — hence an explicit guard.
  it('renders a single root element so vuedraggable can bind to it', () => {
    const wrapper = mount(StudentChip, { props: { student, entry } })

    expect(wrapper.element.nodeType).toBe(Node.ELEMENT_NODE)
    expect(wrapper.element.tagName).toBe('DIV')
    expect(wrapper.classes()).toContain('student-chip')
  })

  // The algorithm returns `score` (88 here: base 100 minus a 12 location
  // penalty) and `objectiveScore` (91: score plus the +3 size bonus). The
  // matcher ranks by objectiveScore and the card's breakdown totals to it, so
  // showing `score` made the badge disagree with its own breakdown.
  it('shows objectiveScore, which includes the size bonus', () => {
    const wrapper = mount(StudentChip, { props: { student, entry } })
    expect(wrapper.find('.student-chip__score').text()).toBe('91')
  })

  it('falls back to score when no breakdown is present', () => {
    const wrapper = mount(StudentChip, {
      props: { student, entry: { ...entry, scoreBreakdown: null } }
    })
    expect(wrapper.find('.student-chip__score').text()).toBe('88')
  })

  it('shows the same total in the badge and the card', async () => {
    const wrapper = mount(StudentChip, { props: { student, entry }, attachTo: document.body })
    await wrapper.trigger('mouseenter')

    const rows = document.body.querySelectorAll('.student-chip-card__row--total')
    // First row is "Match score", last is "Total" — both are objectiveScore.
    expect(rows[0].textContent).toContain('91.00')
    expect(rows[rows.length - 1].textContent).toContain('91.00')

    wrapper.unmount()
  })

  it('omits the score for an existing group member', () => {
    const wrapper = mount(StudentChip, { props: { student, fixed: true } })
    expect(wrapper.find('.student-chip__score').exists()).toBe(false)
  })

  it('highlights a student sitting in their recommended group', () => {
    const wrapper = mount(StudentChip, { props: { student, entry } })
    expect(wrapper.classes()).toContain('student-chip--recommended')
  })

  it('drops the highlight once the student has been moved', () => {
    const wrapper = mount(StudentChip, { props: { student, entry, moved: true } })
    expect(wrapper.classes()).not.toContain('student-chip--recommended')
    expect(wrapper.find('.student-chip__score').classes()).toContain(
      'student-chip__score--moved'
    )
  })

  it('opens the detail card on hover, teleported to body', async () => {
    const wrapper = mount(StudentChip, { props: { student, entry }, attachTo: document.body })

    await wrapper.trigger('mouseenter')

    const card = document.body.querySelector('.student-chip-card')
    expect(card).not.toBeNull()
    expect(card?.textContent).toContain('United States')
    expect(card?.textContent).toContain('Synthetic Biology')

    wrapper.unmount()
  })

  it('does not open the card while a drag is in progress', async () => {
    const wrapper = mount(StudentChip, {
      props: { student, entry, suppressed: true },
      attachTo: document.body
    })

    await wrapper.trigger('mouseenter')

    expect(document.body.querySelector('.student-chip-card')).toBeNull()
    wrapper.unmount()
  })

  it('warns that the score belongs to the original group when moved', async () => {
    const wrapper = mount(StudentChip, {
      props: { student, entry, moved: true, recommendedGroupName: 'BTF15' },
      attachTo: document.body
    })

    await wrapper.trigger('mouseenter')

    expect(document.body.querySelector('.student-chip-card')?.textContent).toContain('BTF15')
    wrapper.unmount()
  })
})
