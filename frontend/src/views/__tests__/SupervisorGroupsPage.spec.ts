import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import SupervisorGroupsPage from '@/views/SupervisorGroupsPage.vue'
import {
  addSupervisedGroupMembers,
  createAllWaitingGroups,
  fetchSupervisedGroups,
  removeSupervisedGroupMembers,
  saveSupervisedGroupOrder,
  type SupervisedGroup,
} from '@/utils/supervisedGroups'
import { fetchSupervisedStudents, type SupervisedStudent } from '@/utils/supervisedStudents'

vi.mock('@/utils/supervisedGroups', () => ({
  fetchSupervisedGroups: vi.fn(),
  createAllWaitingGroups: vi.fn(),
  addSupervisedGroupMembers: vi.fn(),
  removeSupervisedGroupMembers: vi.fn(),
  deleteSupervisedGroup: vi.fn(),
  saveSupervisedGroupOrder: vi.fn(),
}))

vi.mock('@/utils/supervisedStudents', () => ({
  fetchSupervisedStudents: vi.fn(),
  fullName: (first: string, last: string, email: string) => `${first} ${last}`.trim() || email,
}))

vi.mock('@/stores/groups', () => ({
  useGroupsStore: () => ({ load: vi.fn().mockResolvedValue([]), upsert: vi.fn(), groups: [] }),
}))

const student = (
  id: number,
  first: string,
  groupId: number | null,
  home: number | null = groupId,
): SupervisedStudent => ({
  id,
  first_name: first,
  last_name: 'Lee',
  email: `${first.toLowerCase()}@example.test`,
  school_name: 'Example School',
  year_lvl: '10',
  interests: [],
  pg_first_name: '',
  pg_last_name: '',
  pg_email: null,
  parent_guardian_flag: false,
  has_join_permission: false,
  joinperm_response_id: null,
  joinperm_granted_at: null,
  group_id: groupId,
  group_name: null,
  registration_group_id: home,
})

const group = (
  id: number,
  name: string,
  registeredBy: SupervisedGroup['registered_by'],
  { placed = false, studentIds = [] as number[] } = {},
): SupervisedGroup => ({
  id,
  group_name: name,
  members: studentIds.map((studentId) => ({
    id: studentId,
    first_name: '',
    last_name: '',
    email: '',
    role: 'student',
  })),
  interests: [],
  registered_by: registeredBy,
  placed,
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('SupervisorGroupsPage', () => {
  it('keeps groups formed while registering in the Waiting Area, the rest on the board', async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([
      student(1, 'Amy', 10),
      student(2, 'Ben', 11),
      student(3, 'Cara', 12),
      student(4, 'Dan', null),
    ])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([
      group(10, 'BTF89', 'supervisor'),
      group(11, 'BTF93', 'members'),
      group(12, 'BTF01', ''),
    ])
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()

    const waiting = wrapper.get('.waiting-area')
    expect(waiting.findAll('.waiting-section-title').map((title) => title.text())).toEqual([
      'Groups you registered',
      'Groups students formed',
      'Students without a group',
    ])
    // Not named: they aren't BIOTech groups yet.
    expect(waiting.findAll('.waiting-group-label').map((label) => label.text())).toEqual([
      'Group:',
      'Group:',
    ])
    expect(waiting.text()).not.toContain('BTF89')
    expect(waiting.findAll('.waiting-group')[0]!.text()).toContain('Amy Lee')
    // Everyone in the Waiting Area, in its groups or not.
    expect(waiting.get('.waiting-count').text()).toBe('3 Students')
    // The board keeps only the group made later.
    expect(wrapper.findAll('.group-card h2').map((heading) => heading.text())).toEqual(['BTF01'])
  })

  it('sends a student back to where they were in the Waiting Area, and moves nobody within it', async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([
      student(1, 'Amy', 10),
      // Ben registered in BTF89, and was moved to BTF01.
      student(2, 'Ben', 12, 10),
      // Dan registered alone, and was moved to BTF01.
      student(4, 'Dan', 12, null),
    ])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([
      group(10, 'BTF89', 'supervisor'),
      group(11, 'BTF93', 'members'),
      group(12, 'BTF01', ''),
    ])
    vi.mocked(addSupervisedGroupMembers).mockResolvedValue(group(10, 'BTF89', 'supervisor'))
    vi.mocked(removeSupervisedGroupMembers).mockResolvedValue(group(12, 'BTF01', ''))
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()
    const drop = async (studentId: number, selector: string) => {
      await wrapper.get(selector).trigger('drop', { dataTransfer: { getData: () => String(studentId) } })
      await flushPromises()
    }

    // Already in the Waiting Area: dropping it anywhere in it moves nothing.
    await drop(1, '.waiting-area')
    expect(addSupervisedGroupMembers).not.toHaveBeenCalled()
    expect(removeSupervisedGroupMembers).not.toHaveBeenCalled()

    // Back from BTF01: Ben to the group he registered in, Dan to no group.
    await drop(2, '.waiting-area')
    expect(addSupervisedGroupMembers).toHaveBeenCalledWith(10, [2], 'student')
    await drop(4, '.waiting-area')
    expect(removeSupervisedGroupMembers).toHaveBeenCalledWith(12, [4])
  })

  it("puts a student back on their group's line once it's a BIOTech group", async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([student(1, 'Amy', 10), student(2, 'Ben', 10)])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([
      group(10, 'BTF89', 'supervisor', { placed: true, studentIds: [1, 2] }),
    ])
    // Out of BTF89, which keeps Ben.
    vi.mocked(removeSupervisedGroupMembers).mockResolvedValue(
      group(10, 'BTF89', 'supervisor', { placed: true, studentIds: [2] }),
    )
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()
    expect(wrapper.findAll('.group-card h2').map((heading) => heading.text())).toEqual(['BTF89'])
    expect(wrapper.find('.waiting-group').exists()).toBe(false)

    await wrapper.get('.waiting-area').trigger('drop', { dataTransfer: { getData: () => '1' } })
    await flushPromises()

    expect(removeSupervisedGroupMembers).toHaveBeenCalledWith(10, [1])
    expect(wrapper.findAll('.waiting-section-title')[0]!.text()).toBe('Groups you registered')
    expect(wrapper.get('.waiting-group').text()).toContain('Amy Lee')
    expect(wrapper.get('.group-card').text()).toContain('Ben Lee')
  })

  it("creates all of a section's groups, once confirmed, onto the Groups board", async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([student(1, 'Amy', 10), student(2, 'Ben', 11)])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([
      group(10, 'BTF89', 'supervisor'),
      group(11, 'BTF93', 'members'),
    ])
    vi.mocked(createAllWaitingGroups).mockResolvedValue([
      group(10, 'BTF89', 'supervisor', { placed: true, studentIds: [1] }),
    ])
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()

    await wrapper.get('[data-test="create-all-supervisor"]').trigger('click')
    expect(wrapper.get('#create-all-title').text()).toBe('Create 1 group?')
    const confirm = wrapper.findAll('.bulk-delete-actions button').find((b) => b.text() === 'Create groups')!
    await confirm.trigger('click')
    await flushPromises()

    expect(createAllWaitingGroups).toHaveBeenCalledWith('supervisor')
    expect(wrapper.find('#create-all-title').exists()).toBe(false)
    // On the board now, named; the students' groups still wait.
    expect(wrapper.findAll('.group-card h2').map((heading) => heading.text())).toEqual(['BTF89'])
    expect(wrapper.findAll('.waiting-section-title').map((title) => title.text())).toEqual([
      'Groups students formed',
      'Students without a group',
    ])
  })

  it("counts another supervisor's students in a shared group, and won't overfill it", async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([student(1, 'Amy', 12), student(4, 'Dan', null)])
    const shared = group(12, 'BTF01', '', { studentIds: [1] })
    shared.members.push(
      ...['Zoe', 'Yan', 'Xia', 'Wil'].map((first, index) => ({
        id: 90 + index,
        first_name: first,
        last_name: 'Kim',
        email: `${first.toLowerCase()}@other.test`,
        role: 'student',
      })),
    )
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([shared])
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()

    const card = wrapper.get('.group-card')
    // Amy and the other supervisor's four: full.
    expect(card.get('.group-count').text()).toBe('5/5')
    const others = card.findAll('.student-row--other')
    expect(others.map((row) => row.text())).toEqual([
      "Zoe Kim Another supervisor's student",
      "Yan Kim Another supervisor's student",
      "Xia Kim Another supervisor's student",
      "Wil Kim Another supervisor's student",
    ])
    // Not the supervisor's to move.
    expect(others[0]!.attributes('draggable')).toBeUndefined()
    expect(card.find('.drop-hint').exists()).toBe(false)

    await card.trigger('drop', { dataTransfer: { getData: () => '4' } })
    await flushPromises()
    expect(addSupervisedGroupMembers).not.toHaveBeenCalled()
    expect(wrapper.get('.waiting-flash').text()).toBe('This group already has 5 students.')
  })
  it("moves a group into another's place by its handle, and saves the new order", async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([
      group(12, 'BTF01', ''),
      group(13, 'BTF02', ''),
      group(14, 'BTF03', ''),
    ])
    vi.mocked(saveSupervisedGroupOrder).mockResolvedValue(undefined)
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()
    const headings = () => wrapper.findAll('.group-card h2').map((heading) => heading.text())
    const dataTransfer = { setData: vi.fn(), setDragImage: vi.fn(), effectAllowed: '' }

    await wrapper.get('[aria-label="Move BTF01"]').trigger('dragstart', { dataTransfer })
    expect(dataTransfer.setData).toHaveBeenCalledWith('application/x-group', '12')
    expect(dataTransfer.setDragImage).toHaveBeenCalled()
    const cards = wrapper.findAll('.group-card')
    expect(cards[0]!.classes()).toContain('group-card--moving')
    await cards[2]!.trigger('dragover')
    expect(cards[2]!.classes()).toContain('group-card--drop-target')
    // Its own place is no target.
    await cards[0]!.trigger('dragover')
    expect(cards[0]!.classes()).not.toContain('group-card--drop-target')

    await cards[2]!.trigger('drop')
    await flushPromises()
    expect(headings()).toEqual(['BTF02', 'BTF03', 'BTF01'])
    expect(saveSupervisedGroupOrder).toHaveBeenCalledWith([13, 14, 12])
    expect(wrapper.find('.group-card--moving').exists()).toBe(false)
  })

  it('puts the groups back, and says why, when the new order cannot be saved', async () => {
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([group(12, 'BTF01', ''), group(13, 'BTF02', '')])
    vi.mocked(saveSupervisedGroupOrder).mockRejectedValue(new Error('The order could not be saved.'))
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()

    await wrapper.get('[aria-label="Move BTF02"]').trigger('dragstart', { dataTransfer: { setData: vi.fn(), setDragImage: vi.fn() } })
    await wrapper.findAll('.group-card')[0]!.trigger('drop')
    await flushPromises()
    expect(wrapper.findAll('.group-card h2').map((heading) => heading.text())).toEqual(['BTF01', 'BTF02'])
    expect(wrapper.get('.waiting-flash').text()).toBe('The order could not be saved.')

    // A group dropped back on its own place isn't saved at all.
    vi.mocked(saveSupervisedGroupOrder).mockClear()
    await wrapper.get('[aria-label="Move BTF01"]').trigger('dragstart', { dataTransfer: { setData: vi.fn(), setDragImage: vi.fn() } })
    await wrapper.get('[aria-label="Move BTF01"]').trigger('dragend')
    await wrapper.findAll('.group-card')[0]!.trigger('drop', { dataTransfer: { getData: () => '' } })
    await flushPromises()
    expect(saveSupervisedGroupOrder).not.toHaveBeenCalled()
  })

  it('asks before matching a student outside their school, and moves them once confirmed', async () => {
    const dan = { ...student(4, 'Dan', null), school_name: 'Other High' }
    vi.mocked(fetchSupervisedStudents).mockResolvedValue([student(1, 'Amy', 12), dan])
    vi.mocked(fetchSupervisedGroups).mockResolvedValue([group(12, 'BTF01', '', { studentIds: [1] })])
    vi.mocked(addSupervisedGroupMembers).mockResolvedValue(group(12, 'BTF01', '', { studentIds: [1, 4] }))
    const wrapper = mount(SupervisorGroupsPage, {
      global: { stubs: { SupervisorStudentSheet: true, GroupEditorModal: true } },
    })
    await flushPromises()
    const drop = () => wrapper.get('.group-card').trigger('drop', { dataTransfer: { getData: () => '4' } })

    await drop()
    let dialog = wrapper.get('[aria-labelledby="school-match-title"]')
    expect(dialog.get('h3').text()).toBe('Match outside school?')
    expect(dialog.get('p').text()).toBe(
      'Dan Lee is from Other High. BTF01 has students from Example School. ' +
        'Assigning them will match this student outside their school.',
    )
    await dialog.findAll('button').find((button) => button.text() === 'Cancel')!.trigger('click')
    expect(wrapper.find('[aria-labelledby="school-match-title"]').exists()).toBe(false)
    expect(addSupervisedGroupMembers).not.toHaveBeenCalled()

    await drop()
    dialog = wrapper.get('[aria-labelledby="school-match-title"]')
    await dialog.findAll('button').find((button) => button.text() === 'Confirm')!.trigger('click')
    await flushPromises()
    expect(addSupervisedGroupMembers).toHaveBeenCalledWith(12, [4], 'student')
    expect(wrapper.get('.group-card').text()).toContain('Dan Lee')
  })
})
