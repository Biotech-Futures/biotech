import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import AuditPager from '../AuditPager.vue'
import { pageItems } from '../pageItems'

/**
 * The footer under the audit table, ported from adminweb's shared
 * TablePaginationBar (rows per page, "Page N of M", numbered Previous/Next).
 * The page-level spec covers what the audit page does with its events; this
 * one covers the control itself.
 */

function pager(props: Partial<{ page: number; totalPages: number; pageSize: number; disabled: boolean }> = {}) {
  return mount(AuditPager, { props: { page: 1, totalPages: 1, pageSize: 25, ...props } })
}

const buttonLabels = (wrapper: ReturnType<typeof pager>) =>
  wrapper.findAll('nav button').map((button) => button.text())

describe('which page buttons the footer shows', () => {
  it('shows every page while there are seven or fewer', () => {
    expect(pageItems(1, 1)).toEqual([1])
    expect(pageItems(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7])
  })

  it('pins the first and last page and slides a window of three between them', () => {
    expect(pageItems(1, 40)).toEqual([1, 2, 3, 4, 'ellipsis', 40])
    expect(pageItems(20, 40)).toEqual([1, 'ellipsis', 19, 20, 21, 'ellipsis', 40])
    expect(pageItems(40, 40)).toEqual([1, 'ellipsis', 37, 38, 39, 40])
  })

  it('shows a single hidden page inline instead of behind an ellipsis', () => {
    // An ellipsis standing in for one page is a button's width saved and a
    // page made harder to reach.
    expect(pageItems(4, 8)).toEqual([1, 2, 3, 4, 5, 'ellipsis', 8])
    expect(pageItems(5, 8)).toEqual([1, 'ellipsis', 4, 5, 6, 7, 8])
  })
})

describe('AuditPager', () => {
  it('says where the reader is and offers every page around it', () => {
    const wrapper = pager({ page: 20, totalPages: 40 })

    expect(wrapper.find('.audit-pager__info').text()).toBe('Page 20 of 40')
    expect(buttonLabels(wrapper)).toEqual(['Previous', '1', '19', '20', '21', '40', 'Next'])
    expect(wrapper.find('[aria-current="page"]').text()).toBe('20')
    expect(wrapper.find('nav').attributes('aria-label')).toBe('Pagination')
    expect(wrapper.find('button[aria-label="Go to page 21"]').exists()).toBe(true)
  })

  it('asks for the page a button names', async () => {
    const wrapper = pager({ page: 20, totalPages: 40 })

    await wrapper.find('button[aria-label="Go to page 40"]').trigger('click')
    await wrapper.findAll('nav button').at(0)!.trigger('click')
    await wrapper.findAll('nav button').at(-1)!.trigger('click')

    expect(wrapper.emitted('page-change')).toEqual([[40], [19], [21]])
  })

  it('does not step off either end, and keeps both end buttons focusable', async () => {
    // aria-disabled, not disabled: switching off the button that has focus
    // drops a keyboard reader back to the top of the document.
    const first = pager({ page: 1, totalPages: 3 })
    const previous = first.findAll('nav button').at(0)!
    expect(previous.attributes('aria-disabled')).toBe('true')
    expect(previous.attributes('disabled')).toBeUndefined()
    await previous.trigger('click')
    expect(first.emitted('page-change')).toBeUndefined()

    const last = pager({ page: 3, totalPages: 3 })
    const next = last.findAll('nav button').at(-1)!
    expect(next.attributes('aria-disabled')).toBe('true')
    await next.trigger('click')
    expect(last.emitted('page-change')).toBeUndefined()
  })

  it('does nothing while the page behind it loads', async () => {
    const wrapper = pager({ page: 2, totalPages: 5, disabled: true })

    for (const button of wrapper.findAll('nav button')) {
      expect(button.attributes('aria-disabled')).toBe('true')
      await button.trigger('click')
    }
    expect(wrapper.emitted('page-change')).toBeUndefined()
  })

  it('offers the React presets and a custom size under a visible label', async () => {
    const wrapper = pager()
    const select = wrapper.find('select')

    const label = wrapper.find('label')
    expect(label.text()).toBe('Rows per page')
    expect(label.attributes('for')).toBe(select.attributes('id'))
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      '25 / page',
      '50 / page',
      '100 / page',
      '200 / page',
      'Custom…'
    ])

    await select.setValue('100')
    expect(wrapper.emitted('page-size-change')).toEqual([[100]])
  })

  it('names a size in force that is not a preset instead of going blank', async () => {
    // The server decides the size in the end, and the page hands the control
    // whatever it served. Opened on such a size, the control starts on the
    // number box, as React's did; met while the presets are showing, the size
    // gets an option of its own rather than a blank select.
    const opened = pager({ pageSize: 10 })
    expect(opened.find('select').exists()).toBe(false)
    expect((opened.find('input').element as HTMLInputElement).value).toBe('10')

    const later = pager()
    await later.setProps({ pageSize: 10 })
    const select = later.find('select')
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      '10 / page',
      '25 / page',
      '50 / page',
      '100 / page',
      '200 / page',
      'Custom…'
    ])
    expect((select.element as HTMLSelectElement).value).toBe('10')
  })
})

describe('a custom number of rows per page', () => {
  let wrapper: ReturnType<typeof pager> | null = null

  function attached(props: Partial<{ pageSize: number }> = {}) {
    wrapper = mount(AuditPager, {
      props: { page: 1, totalPages: 1, pageSize: 25, ...props },
      attachTo: document.body
    })
    return wrapper
  }

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  const box = (w: ReturnType<typeof pager>) => w.find('input[type="number"]')

  it('swaps the select for a number box, focused and holding the current size', async () => {
    // The select that had focus is gone once Custom… is picked, so focus goes
    // to the box that replaces it rather than to the top of the document.
    // The size in force changes after the control opens (the server's answer
    // lands), and the box holds the new one, not the one it opened with.
    const w = attached()
    await w.setProps({ pageSize: 50 })
    await w.find('select').setValue('custom')
    await nextTick()

    const input = box(w)
    expect((input.element as HTMLInputElement).value).toBe('50')
    expect(input.attributes('min')).toBe('1')
    expect(input.attributes('max')).toBe('500')
    expect(w.find('label').attributes('for')).toBe(input.attributes('id'))
    expect(document.activeElement).toBe(input.element)
    // Picking Custom… is not a size.
    expect(w.emitted('page-size-change')).toBeUndefined()
  })

  it('asks for the typed size on Enter and when the box loses focus', async () => {
    const w = attached()
    await w.find('select').setValue('custom')

    await box(w).setValue('75')
    await box(w).trigger('keydown', { key: 'Enter' })
    await box(w).setValue('40')
    await box(w).trigger('blur')

    expect(w.emitted('page-size-change')).toEqual([[75], [40]])
  })

  it('keeps the size to a whole number from 1 to 500, as React did', async () => {
    const w = attached()
    await w.find('select').setValue('custom')

    for (const typed of ['900', '0', '7.9']) {
      await box(w).setValue(typed)
      await box(w).trigger('keydown', { key: 'Enter' })
    }

    expect(w.emitted('page-size-change')).toEqual([[500], [1], [7]])
    // And the box says what was asked for, not what was typed.
    expect((box(w).element as HTMLInputElement).value).toBe('7')
  })

  it('asks for nothing when the typed size is the one in force', async () => {
    const w = attached()
    await w.find('select').setValue('custom')

    await box(w).setValue('25')
    await box(w).trigger('keydown', { key: 'Enter' })

    expect(w.emitted('page-size-change')).toBeUndefined()
  })

  it('goes back to the presets, and to the first of them when the box held another size', async () => {
    // A size the presets cannot show cannot stay in force behind them, so
    // leaving the box goes back to 25, as React did. Focus goes to the select
    // that replaces the Presets button.
    const w = attached({ pageSize: 75 })
    await w.find('button').trigger('click')
    await nextTick()

    expect(w.emitted('page-size-change')).toEqual([[25]])
    expect(box(w).exists()).toBe(false)
    expect(document.activeElement).toBe(w.find('select').element)
  })

  it('leaves the size alone when going back from a preset', async () => {
    const w = attached()
    await w.find('select').setValue('custom')
    await w.find('button').trigger('click')
    await nextTick()

    expect(w.emitted('page-size-change')).toBeUndefined()
    expect(document.activeElement).toBe(w.find('select').element)
  })

  it('returns to the presets when the size in force becomes one, keeping focus', async () => {
    // Custom 300 is asked for, and the server answers with 100. The page
    // hands the control 300 while the page loads and 100 once it lands; 100
    // is a preset, so the select comes back naming it, and the reader who
    // pressed Enter in the box lands on that select.
    const w = attached()
    await w.find('select').setValue('custom')
    await nextTick()
    await box(w).setValue('300')
    await box(w).trigger('keydown', { key: 'Enter' })
    expect(w.emitted('page-size-change')).toEqual([[300]])

    await w.setProps({ pageSize: 300 })
    expect((box(w).element as HTMLInputElement).value).toBe('300')

    await w.setProps({ pageSize: 100 })
    await nextTick()
    const select = w.find('select')
    expect((select.element as HTMLSelectElement).value).toBe('100')
    expect(document.activeElement).toBe(select.element)
  })
})
