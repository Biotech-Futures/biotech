import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'school', label: 'School' }
]
const rows = [
  { id: 1, name: 'Ada', school: 'North' },
  { id: 2, name: 'Bob', school: 'South' }
]

const mountTable = (props: Record<string, unknown> = {}) =>
  mount(AppDataTable, { props: { columns, rows, selectable: false, ...props } })

describe('rows per page', () => {
  const pageSizeOptions = (wrapper: ReturnType<typeof mountTable>) =>
    wrapper.findAll('.data-table-page-size option').map((option) => option.text())

  it('offers All by default, as every other table does', () => {
    expect(pageSizeOptions(mountTable())).toContain('All')
  })

  it('leaves All out when a page turns it off', () => {
    const options = pageSizeOptions(mountTable({ allowAllRows: false }))

    expect(options).not.toContain('All')
    expect(options.length).toBeGreaterThan(0)
  })
})
