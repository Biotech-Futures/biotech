import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, reactive, ref } from 'vue'
import AdminMentorsView from '@/views/admin/AdminMentorsView.vue'

const mocks = vi.hoisted(() => ({
  load: vi.fn()
}))

vi.mock('@/components/admin/mentors/AdminMentorImportSheet.vue', () => ({
  default: {
    name: 'AdminMentorImportSheet',
    props: ['modelValue'],
    emits: ['update:modelValue', 'imported'],
    template: '<div data-testid="mentor-import-sheet" :data-open="String(modelValue)"></div>'
  }
}))

vi.mock('@/composables/admin/useAdminMentorsView', () => ({
  useAdminMentorsView: () => ({
    loading: ref(false),
    statusBusy: ref(false),
    error: ref(''),
    mentors: ref([]),
    mentorList: ref([]),
    inactiveDays: ref(30),
    expandedIds: ref(new Set()),
    selectedIds: ref(new Set()),
    bulkAction: reactive({ open: false, action: 'activate', count: 0 }),
    replaceDialogOpen: ref(false),
    inactiveGroups: computed(() => []),
    sortedMentors: computed(() => []),
    headerChecked: computed(() => false),
    setSort: vi.fn(),
    toggleExpand: vi.fn(),
    toggleAll: vi.fn(),
    toggleOne: vi.fn(),
    clearSelection: vi.fn(),
    onInactiveDaysChange: vi.fn(),
    toggleActive: vi.fn(),
    openBulk: vi.fn(),
    bulkTitle: computed(() => 'Activate 0 mentors?'),
    bulkMessage: computed(() => 'The selected mentors will be able to sign in again.'),
    runBulkStatus: vi.fn(),
    onReplaceConfirmed: vi.fn(),
    sortClass: vi.fn(() => ({})),
    sortIcon: vi.fn(() => 'fa-sort'),
    load: mocks.load
  })
}))

describe('AdminMentorsView CSV import wiring', () => {
  it('opens the mentor import sheet and reloads mentors after import', async () => {
    mocks.load.mockClear()
    const wrapper = mount(AdminMentorsView)

    expect(mocks.load).toHaveBeenCalledTimes(1)
    const button = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Import Mentors CSV'))
    expect(button).toBeTruthy()
    expect(wrapper.find('[data-testid="mentor-import-sheet"]').attributes('data-open')).toBe('false')

    await button!.trigger('click')
    expect(wrapper.find('[data-testid="mentor-import-sheet"]').attributes('data-open')).toBe('true')

    wrapper.findComponent({ name: 'AdminMentorImportSheet' }).vm.$emit('imported', {
      msg: 'Bulk import complete: 1 created, 0 skipped',
      data: { created: [], skipped: [] }
    })

    expect(mocks.load).toHaveBeenCalledTimes(2)
  })
})
