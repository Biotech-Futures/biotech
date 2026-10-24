import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AdminDataTable from '@/components/admin/AdminDataTable.vue'
import { appSelectText, pickAppSelect } from '@/__tests__/appSelect'

const columns = [{ key: 'name', label: 'Name' }]
const rows = (count: number) => Array.from({ length: count }, (_, i) => ({ id: i + 1, name: `Name ${i + 1}` }))

const mountTable = (count: number, totalCount = count) =>
  mount(AdminDataTable, { props: { columns, rows: rows(Math.min(count, 25)), totalCount, pageSize: 25 } })

const picker = (wrapper: ReturnType<typeof mountTable>) => wrapper.find('.admin-table__page-size .app-select')

describe('rows per page', () => {
  it('reads as the rows there are, and is off, while they all fit on one page', () => {
    const wrapper = mountTable(8)
    expect(appSelectText(wrapper, '.admin-table__page-size')).toBe('8')
    expect(picker(wrapper).classes()).toContain('is-disabled')
  })

  it('shows its size, and is on, with more than one page', () => {
    const wrapper = mountTable(25, 60)
    expect(appSelectText(wrapper, '.admin-table__page-size')).toBe('25')
    expect(picker(wrapper).classes()).not.toContain('is-disabled')
  })

  it('stays on once a size is picked, so it can be changed back', async () => {
    const wrapper = mountTable(25, 60)
    await pickAppSelect(wrapper, '.admin-table__page-size', '100')
    expect(wrapper.emitted('page-size-change')?.[0]).toEqual([100])
    await wrapper.setProps({ pageSize: 100 })
    expect(appSelectText(wrapper, '.admin-table__page-size')).toBe('100')
    expect(picker(wrapper).classes()).not.toContain('is-disabled')
  })
})
