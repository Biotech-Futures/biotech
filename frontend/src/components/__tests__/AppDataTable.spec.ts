import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import { DATA_TABLE_ALL } from '@/utils/dataTable'

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

describe('the bottom bar', () => {
  const many = Array.from({ length: 12 }, (_, i) => ({ id: i + 1, icon: 'x', name: `Name ${i + 1}`, school: 'S' }))

  it('offers rows per page as Entries', async () => {
    const wrapper = mountTable({ rows: many, pageSize: 5 })
    expect(await appSelectLabels(wrapper, '.data-table-page-size')).toEqual([
      '5 Entries',
      '7 Entries',
      '15 Entries',
      '30 Entries',
      'All Entries'
    ])
    expect(wrapper.find('.data-table-summary').text()).toBe('1 - 5 out of 12')
  })

  it('caps rows per page to maxPageSize and drops the All choice', async () => {
    const wrapper = mountTable({ rows: many, pageSize: 5, totalCount: 12, page: 1, maxPageSize: 10 })
    expect(await appSelectLabels(wrapper, '.data-table-page-size')).toEqual([
      '5 Entries',
      '7 Entries'
    ])
  })

  const picker = (wrapper: ReturnType<typeof mountTable>) => wrapper.find('.data-table-page-size .app-select')

  it('reads as the rows there are, and is off, while they all fit on one page', () => {
    const wrapper = mountTable({ rows: many.slice(0, 8), pageSize: 10 })
    expect(wrapper.find('.data-table-summary').text()).toBe('1 - 8 out of 8')
    expect(appSelectText(wrapper, '.data-table-page-size')).toBe('8 Entries')
    expect(picker(wrapper).classes()).toContain('is-disabled')
  })

  it('shows its own size, and is on, with more than one page', () => {
    const wrapper = mountTable({ rows: many, pageSize: 10 })
    expect(appSelectText(wrapper, '.data-table-page-size')).toBe('10 Entries')
    expect(picker(wrapper).classes()).not.toContain('is-disabled')
  })

  it('turns to the page with focusRow and brings it into view, then lets go once someone pages', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    const wrapper = mountTable({ rows: many, pageSize: 5, focusRow: 9 })
    await flushPromises()
    expect(wrapper.find('.data-table-summary').text()).toBe('6 - 10 out of 12')
    expect(wrapper.get('tr.data-table-row--focused').attributes('data-row-key')).toBe('9')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'center' })

    // Paged on, a change of rows doesn't pull them back to it.
    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await wrapper.setProps({ rows: [...many] })
    await flushPromises()
    expect(wrapper.find('.data-table-summary').text()).toBe('11 - 12 out of 12')
  })

  // Rows, headings, bottom bar and scrollbar each 56px: 10 rows fit the
  // 768px window (600px of room under the headings and above the bar).
  const rowsOf56px = () => vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(56)

  it('stays on for a table on All whose rows run past the screen', async () => {
    rowsOf56px()
    const wrapper = mountTable({ rows: many, pageSize: DATA_TABLE_ALL })
    await flushPromises()
    expect(wrapper.find('.data-table-summary').text()).toBe('1 - 12 out of 12')
    expect(appSelectText(wrapper, '.data-table-page-size')).toBe('All Entries')
    expect(picker(wrapper).classes()).not.toContain('is-disabled')
  })

  it('is off for a table on All whose rows are all on screen', async () => {
    rowsOf56px()
    const wrapper = mountTable({ rows: many.slice(0, 8), pageSize: DATA_TABLE_ALL })
    await flushPromises()
    expect(picker(wrapper).classes()).toContain('is-disabled')
  })

  it('keeps a picked size as picked, on one page too, and stays on to change it back', async () => {
    const wrapper = mountTable({ rows: many, pageSize: 10 })
    await pickAppSelect(wrapper, '.data-table-page-size', '15 Entries')
    expect(wrapper.find('.data-table-summary').text()).toBe('1 - 12 out of 12')
    expect(appSelectText(wrapper, '.data-table-page-size')).toBe('15 Entries')
    expect(picker(wrapper).classes()).not.toContain('is-disabled')
  })

  // Turns a page with the bar at ``from`` on screen, drawn at ``to`` on the
  // next, scrolled ``scrolled`` down; the table box ``tall`` px.
  const turnPage = async (from: number, to: number, scrolled: number, tall = 230) => {
    const scrollBy = vi.spyOn(window, 'scrollBy').mockImplementation(() => {})
    Object.defineProperty(window, 'scrollY', { configurable: true, value: scrolled })
    const wrapper = mountTable({ rows: many, pageSize: 5 })
    const bar = wrapper.find('.data-table-bottom').element as HTMLElement
    const box = wrapper.find('.data-table-wrap').element as HTMLElement
    Object.defineProperty(box, 'offsetHeight', { configurable: true, value: tall })
    vi.spyOn(bar, 'getBoundingClientRect')
      .mockReturnValueOnce({ top: from } as DOMRect)
      .mockReturnValueOnce({ top: to } as DOMRect)
    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    return { wrapper, box, scrollBy }
  }

  afterEach(() => {
    vi.restoreAllMocks()
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 0 })
  })

  it('stays where it is on screen when a page is taller, scrolling down by as much', async () => {
    const { wrapper, box, scrollBy } = await turnPage(500, 560, 0)
    expect(wrapper.find('.data-table-page-info').text()).toBe('Page 2 of 3')
    expect(scrollBy).toHaveBeenCalledWith(0, 60)
    expect(box.style.minHeight).toBe('')
  })

  it('stays where it is on screen when a page is shorter, scrolling up rather than leaving room', async () => {
    const { box, scrollBy } = await turnPage(500, 400, 300)
    expect(scrollBy).toHaveBeenCalledWith(0, -100)
    expect(box.style.minHeight).toBe('')
  })

  it('near the top, scrolls up as far as it can and keeps room for the rest', async () => {
    const { wrapper, box, scrollBy } = await turnPage(500, 400, 30)
    expect(scrollBy).toHaveBeenCalledWith(0, -30)
    // 70px it couldn't scroll up by, held below the rows.
    expect(box.style.minHeight).toBe('300px')

    // A new search lets that room go.
    await wrapper.find('.data-table-search-input').setValue('Name 1')
    await flushPromises()
    expect(box.style.minHeight).toBe('')
  })
})
