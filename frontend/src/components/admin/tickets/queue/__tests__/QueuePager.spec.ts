import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import QueuePager from '../QueuePager.vue'

/** The footer and its rows-per-page control on their own. Ported from
 *  adminweb's pagination-nav and PageSizeSelect, which had no tests of their
 *  own there; the queue page specs drive them end to end. */

let wrapper: VueWrapper | null = null

function show(props: { page?: number; totalPages?: number; pageSize?: number; disabled?: boolean } = {}) {
  wrapper = mount(QueuePager, {
    attachTo: document.body,
    props: { page: 1, totalPages: 3, pageSize: 10, disabled: false, ...props }
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

function control() {
  return wrapper!.get('[aria-label="Rows per page"]')
}

function sizes() {
  return (wrapper!.emitted('page-size-change') ?? []).map(([size]) => size)
}

describe('the numbered navigation', () => {
  it('marks the page being read, and names every number as a place to go', () => {
    show({ page: 2, totalPages: 3 })

    const numbers = wrapper!.findAll('button[aria-label^="Go to page"]')
    expect(numbers.map((b) => [b.attributes('aria-label'), b.attributes('aria-current')])).toEqual([
      ['Go to page 1', undefined],
      ['Go to page 2', 'page'],
      ['Go to page 3', undefined]
    ])
  })

  it('hides the gap marker from a screen reader', () => {
    show({ page: 10, totalPages: 20 })

    const gaps = wrapper!.findAll('.queue-pager__gap')
    expect(gaps.length).toBe(2)
    expect(gaps.every((gap) => gap.attributes('aria-hidden') === 'true')).toBe(true)
  })

  it('reports each click as the page it asks for', async () => {
    show({ page: 2, totalPages: 3 })
    const byText = (text: string) => wrapper!.findAll('button').find((b) => b.text() === text)!

    await byText('Previous').trigger('click')
    await byText('Next').trigger('click')
    await wrapper!.get('button[aria-label="Go to page 3"]').trigger('click')

    expect(wrapper!.emitted('page-change')).toEqual([[1], [3], [3]])
  })
})

describe('the rows-per-page control', () => {
  it('opens as the number box on a size that is not a preset', () => {
    show({ pageSize: 10 })

    expect(control().element.tagName).toBe('INPUT')
    expect((control().element as HTMLInputElement).value).toBe('10')
  })

  it('opens as the dropdown on a preset, offering nothing past the server’s cap', () => {
    show({ pageSize: 25 })

    expect(control().element.tagName).toBe('SELECT')
    expect(control().findAll('option').map((o) => o.text())).toEqual([
      '25 / page',
      '50 / page',
      '100 / page',
      'Custom…'
    ])
  })

  it('applies a typed size on Enter, and only when it changed', async () => {
    show({ pageSize: 10 })

    await control().setValue('10')
    await control().trigger('keydown', { key: 'Enter' })
    await control().setValue('33')
    await control().trigger('keydown', { key: 'Enter' })

    expect(sizes()).toEqual([33])
  })

  it('applies a typed size when the box loses focus', async () => {
    show({ pageSize: 10 })

    await control().setValue('40')
    await control().trigger('blur')

    expect(sizes()).toEqual([40])
  })

  it('holds a typed size inside 1 to 100, and reads back what it holds', async () => {
    show({ pageSize: 10 })

    await control().setValue('500')
    await control().trigger('keydown', { key: 'Enter' })

    expect(sizes()).toEqual([100])
    expect((control().element as HTMLInputElement).value).toBe('100')
  })

  it('switches to the number box from Custom, and puts the agent in it', async () => {
    show({ pageSize: 25 })

    await control().setValue('custom')
    await flushPromises()

    expect(control().element.tagName).toBe('INPUT')
    expect(document.activeElement).toBe(control().element)
    expect(sizes()).toEqual([])
  })

  it('goes back to the presets on the first one when the size is not a preset', async () => {
    show({ pageSize: 10 })

    await wrapper!.findAll('button').find((b) => b.text() === 'Presets')!.trigger('click')

    expect(sizes()).toEqual([25])
  })

  it('reports a preset picked from the dropdown', async () => {
    show({ pageSize: 25 })

    await control().setValue('100')

    expect(sizes()).toEqual([100])
  })

  it('holds still while a page is loading', () => {
    show({ disabled: true })

    expect((control().element as HTMLInputElement).disabled).toBe(true)
    expect(
      wrapper!.findAll<HTMLButtonElement>('button').every((b) => b.element.disabled)
    ).toBe(true)
  })
})
