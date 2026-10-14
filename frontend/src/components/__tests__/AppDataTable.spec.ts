import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'

const columns: DataTableColumn[] = [
  { key: 'icon', label: '' },
  { key: 'name', label: 'Name' },
  { key: 'school', label: 'School' }
]
const rows = [
  { id: 1, icon: 'a', name: 'Ada', school: 'North', open: true },
  { id: 2, icon: 'b', name: 'Bob', school: 'South', open: false }
]

const mountTable = (props: Record<string, unknown> = {}, slots: Record<string, string> = {}) =>
  mount(AppDataTable, { props: { columns, rows, selectable: false, ...props }, slots })

const bodyRows = (wrapper: ReturnType<typeof mountTable>) => wrapper.findAll('tr.data-table-row')
const primaryCells = (wrapper: ReturnType<typeof mountTable>) =>
  bodyRows(wrapper).map((row) => row.find('.data-table-cell--primary').text())

describe('rows that open something', () => {
  it('marks them, and the first column as the cell that names them, and opens them on click', async () => {
    const wrapper = mountTable({ clickableRows: true })

    expect(bodyRows(wrapper).every((row) => row.classes('data-table-row--opens'))).toBe(true)
    expect(primaryCells(wrapper)).toEqual(['a', 'b'])

    await bodyRows(wrapper)[1]!.trigger('click')
    expect(wrapper.emitted('row-click')?.[0]?.[0]).toMatchObject({ id: 2 })
  })

  it('names them by the column marked primary instead', () => {
    const wrapper = mountTable({
      clickableRows: true,
      columns: [columns[0], { ...columns[1], primary: true }, columns[2]]
    })

    expect(primaryCells(wrapper)).toEqual(['Ada', 'Bob'])
  })

  it('opens only the rows rowClickable allows', async () => {
    const wrapper = mountTable({ clickableRows: true, rowClickable: (row: { open: boolean }) => row.open })
    const [ada, bob] = bodyRows(wrapper)

    expect(ada!.classes()).toContain('data-table-row--opens')
    expect(bob!.classes()).not.toContain('data-table-row--opens')
    expect(bob!.classes()).not.toContain('data-table-row--clickable')

    await bob!.trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
    await ada!.trigger('click')
    expect(wrapper.emitted('row-click')).toHaveLength(1)
  })

  it('opens a row from its details too, when they are always shown', async () => {
    const wrapper = mountTable(
      { clickableRows: true, showAllDetails: true },
      { 'row-detail': '<span class="detail">More</span>' }
    )
    const detail = wrapper.find('tr.data-table-detail-row')

    expect(detail.classes()).toContain('data-table-detail-row--opens')
    await detail.trigger('click')
    expect(wrapper.emitted('row-click')?.[0]?.[0]).toMatchObject({ id: 1 })
  })

  it('leaves rows that open nothing unmarked', async () => {
    const wrapper = mountTable()

    expect(bodyRows(wrapper).some((row) => row.classes('data-table-row--opens'))).toBe(false)
    await bodyRows(wrapper)[0]!.trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
  })
})
