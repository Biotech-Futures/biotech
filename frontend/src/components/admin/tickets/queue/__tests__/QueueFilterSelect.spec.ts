import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import QueueFilterSelect from '../QueueFilterSelect.vue'
import type { FilterOption } from '../queueFilters'

/** The queue's list with check boxes (C-27), drawn as AppSelect is (C-29). */

const OPTIONS: FilterOption[] = [
  { value: 'high', label: 'High' },
  { value: 'normal', label: 'Normal' },
  { value: 'low', label: 'Low' }
]

let wrapper: VueWrapper | null = null

function show(modelValue: string[] = [], attrs: Record<string, string> = {}) {
  wrapper = mount(QueueFilterSelect, {
    props: { modelValue, options: OPTIONS, anyLabel: 'Any priority' },
    attrs: { 'aria-label': 'Filter by priority', class: 'page-box', 'data-test': 'priority', ...attrs },
    attachTo: document.body
  })
  return wrapper
}

const button = () => wrapper!.get('button')
const list = () => wrapper!.find('[role="group"]')
const checks = () => wrapper!.findAll<HTMLInputElement>('input[type="checkbox"]')

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('the box', () => {
  it('says what is ticked, and is named for the filter it is', () => {
    show(['high'])

    expect(button().text()).toBe('High')
    expect(button().attributes('aria-label')).toBe('Filter by priority')
    // What is ticked is read out after the name, from the words on the box.
    const describedBy = button().attributes('aria-describedby')!
    expect(wrapper!.get(`[id="${describedBy}"]`).text()).toBe('High')
  })

  it('takes the page’s class and data-test on the box, and the rest on the button', () => {
    show()

    expect(wrapper!.classes()).toContain('page-box')
    expect(wrapper!.attributes('data-test')).toBe('priority')
    expect(wrapper!.attributes('aria-label')).toBeUndefined()
  })

  it('follows the ticks it is given', async () => {
    show([])
    expect(button().text()).toBe('Any priority')

    await wrapper!.setProps({ modelValue: ['high', 'normal'] })

    expect(button().text()).toBe('Not Low')
  })
})

describe('opening and closing', () => {
  it('opens on a click, says so, and names its list', async () => {
    show()
    expect(list().exists()).toBe(false)
    expect(button().attributes('aria-expanded')).toBe('false')

    await button().trigger('click')

    expect(button().attributes('aria-expanded')).toBe('true')
    expect(list().attributes('aria-label')).toBe('Filter by priority')
    expect(button().attributes('aria-controls')).toBe(list().attributes('id'))
  })

  it('opens from a press on the box around the words too', async () => {
    show()

    await wrapper!.trigger('mousedown', { button: 0 })

    expect(list().exists()).toBe(true)
  })

  it('stays open while boxes are ticked, so several can be', async () => {
    show()
    await button().trigger('click')

    await checks()[0].setValue(true)
    await checks()[2].setValue(true)

    expect(list().exists()).toBe(true)
    expect(wrapper!.emitted('change')).toEqual([[['high']], [['low']]])
  })

  it('closes on Escape and hands focus back to the box', async () => {
    show()
    await button().trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(checks()[0].element)

    await checks()[0].trigger('keydown', { key: 'Escape' })

    expect(list().exists()).toBe(false)
    expect(document.activeElement).toBe(button().element)
  })

  it('closes on a press elsewhere on the page, and not on one inside it', async () => {
    show()
    await button().trigger('click')

    list().element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await wrapper!.vm.$nextTick()
    expect(list().exists()).toBe(true)

    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    await wrapper!.vm.$nextTick()
    expect(list().exists()).toBe(false)
  })

  it('closes when focus leaves it, and not while it moves between its boxes', async () => {
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    show()
    await button().trigger('keydown', { key: 'ArrowDown' })

    await checks()[0].trigger('focusout', { relatedTarget: checks()[1].element })
    expect(list().exists()).toBe(true)

    await checks()[1].trigger('focusout', { relatedTarget: outside })
    expect(list().exists()).toBe(false)
    outside.remove()
  })

  it('walks its boxes with the arrow keys', async () => {
    show()
    await button().trigger('keydown', { key: 'ArrowDown' })

    await list().trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(checks()[1].element)
    await list().trigger('keydown', { key: 'ArrowDown' })
    await list().trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(checks()[2].element)
    await list().trigger('keydown', { key: 'ArrowUp' })
    expect(document.activeElement).toBe(checks()[1].element)
  })
})

describe('ticking', () => {
  it('sends everything now ticked, in the list’s order', async () => {
    show(['low'])
    await button().trigger('click')

    await checks()[0].setValue(true)

    expect(wrapper!.emitted('update:modelValue')).toEqual([[['high', 'low']]])
    expect(wrapper!.emitted('change')).toEqual([[['high', 'low']]])
  })

  it('takes a box’s own state, so the same change twice cannot flip it back', async () => {
    show(['high'])
    await button().trigger('click')

    // A second change event for a box already ticked, as a double fire would
    // send it. setValue sends nothing for a box already in that state.
    checks()[0].element.checked = true
    await checks()[0].trigger('change')

    expect(wrapper!.emitted('change')).toEqual([[['high']]])
  })

  it('keeps a value the list does not have yet', async () => {
    show(['7'])
    await button().trigger('click')

    await checks()[1].setValue(true)

    expect(wrapper!.emitted('change')).toEqual([[['normal', '7']]])
  })
})
