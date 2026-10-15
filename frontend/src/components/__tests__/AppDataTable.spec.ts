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
  it('marks them, and the first column as the cell that names them, which alone opens them', async () => {
    const wrapper = mountTable({ clickableRows: true })
    const bob = bodyRows(wrapper)[1]!

    expect(bodyRows(wrapper).every((row) => row.classes('data-table-row--opens'))).toBe(true)
    expect(primaryCells(wrapper)).toEqual(['a', 'b'])

    // Elsewhere on the row: nothing.
    await bob.trigger('click')
    await bob.findAll('td')[2]!.trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()

    await bob.find('.data-table-cell--primary').trigger('click')
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

    await bob!.find('.data-table-cell--primary').trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
    await ada!.find('.data-table-cell--primary').trigger('click')
    expect(wrapper.emitted('row-click')).toHaveLength(1)
  })

  it('does not open a row from its details', async () => {
    const wrapper = mountTable(
      { clickableRows: true, showAllDetails: true },
      { 'row-detail': '<span class="detail">More</span>' }
    )

    await wrapper.find('tr.data-table-detail-row').trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
  })

  it('starts joined details under the first value, past the tick box column', () => {
    const wrapper = mountTable(
      { selectable: true, joinedDetails: true },
      { 'row-detail': '<span class="detail">More</span>' }
    )
    const cells = wrapper.find('tr.data-table-detail-row').findAll('td')

    expect(cells).toHaveLength(2)
    expect(cells[0]!.classes()).toContain('data-table-check-col')
    expect(cells[0]!.text()).toBe('')
    expect(cells[1]!.attributes('colspan')).toBe(String(columns.length))
    expect(cells[1]!.text()).toBe('More')
  })

  it('leaves rows that open nothing unmarked', async () => {
    const wrapper = mountTable()

    expect(bodyRows(wrapper).some((row) => row.classes('data-table-row--opens'))).toBe(false)
    await bodyRows(wrapper)[0]!.find('.data-table-cell--primary').trigger('click')
    expect(wrapper.emitted('row-click')).toBeUndefined()
  })
})
