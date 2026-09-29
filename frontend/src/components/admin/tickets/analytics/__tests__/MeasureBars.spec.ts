import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import MeasureBars from '../MeasureBars.vue'
import { duration } from '../analyticsFormat'

/**
 * The chart on its own: rows in, bars, axis and table out.
 *
 * React never tested this component. Its page test replaced it with a text
 * stub because recharts draws nothing at the zero width jsdom reports. These
 * bars are CSS widths, so jsdom renders them and they can be read back.
 */

const rowsOf = (wrapper: ReturnType<typeof mount>) =>
  wrapper
    .find('[data-testid="measure-table"]')
    .findAll('tr')
    .map((tr) => `${tr.find('th').text()}|${tr.find('td').text()}`)

describe('MeasureBars', () => {
  it('says the window is empty rather than drawing an empty chart', () => {
    const wrapper = mount(MeasureBars, { props: { label: 'By category', rows: [] } })

    expect(wrapper.text()).toBe('Nothing in this window.')
    expect(wrapper.find('[data-testid="measure-bars-chart"]').exists()).toBe(false)
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('takes a sentence of its own for the empty case', () => {
    const wrapper = mount(MeasureBars, {
      props: { label: 'Time since anything happened', rows: [], emptyMessage: 'Nothing open in this window.' }
    })

    expect(wrapper.text()).toBe('Nothing open in this window.')
  })

  it('draws one bar per row, in the order delivered, each as long as its share of the scale', () => {
    // Commonest first is the server's order; the chart does not re-sort. The
    // scale for a largest value of 4 runs to exactly 4, so the widths are
    // the plain fractions.
    const wrapper = mount(MeasureBars, {
      props: {
        label: 'By channel',
        rows: [
          { label: 'Portal', value: 4 },
          { label: 'Email', value: 2 },
          { label: 'Raised by screening', value: 1 }
        ]
      }
    })

    expect(wrapper.findAll('.measure-bars__label').map((label) => label.text())).toEqual([
      'Portal',
      'Email',
      'Raised by screening'
    ])
    expect(
      wrapper.findAll('[data-testid="measure-bar"]').map((bar) => bar.attributes('style'))
    ).toEqual(['width: 100%;', 'width: 50%;', 'width: 25%;'])
    // A grid line under every tick, vertical only: a reading aid, not a mark.
    expect(
      wrapper.findAll('.measure-bars__gridline').map((line) => line.attributes('style'))
    ).toEqual(['left: 0%;', 'left: 25%;', 'left: 50%;', 'left: 75%;', 'left: 100%;'])
    expect(wrapper.findAll('.measure-bars__value').map((value) => value.text())).toEqual([
      '4',
      '2',
      '1'
    ])
  })

  it('runs the axis, the printed values and the table through the same formatter', () => {
    // React's durations chart once ran its axis "0 / 70000 / 140000" in raw
    // seconds while every other number on the page read "33h 58m".
    const wrapper = mount(MeasureBars, {
      props: {
        label: 'Time since anything happened',
        rows: [
          { label: 'Open', value: 7200 },
          { label: 'In progress', value: 3600 }
        ],
        format: duration
      }
    })

    expect(wrapper.findAll('[data-testid="measure-tick"]').map((tick) => tick.text())).toEqual([
      '0m',
      '33m',
      '1h 7m',
      '1h 40m',
      '2h 13m'
    ])
    expect(wrapper.findAll('.measure-bars__value').map((value) => value.text())).toEqual([
      '2h',
      '1h'
    ])
    expect(rowsOf(wrapper)).toEqual(['Open|2h', 'In progress|1h'])
  })

  it('prints the unit after the value beside the bar and in the table', () => {
    const wrapper = mount(MeasureBars, {
      props: { label: 'Broken down by region', rows: [{ label: 'Australia', value: 5 }], unit: 'tickets' }
    })

    expect(wrapper.find('.measure-bars__value').text()).toBe('5 tickets')
    expect(rowsOf(wrapper)).toEqual(['Australia|5 tickets'])
  })

  it('keeps the numbers readable without the drawing', () => {
    const wrapper = mount(MeasureBars, {
      props: {
        label: 'By category',
        rows: [
          { label: 'Account and access', value: 4 },
          { label: 'Registration', value: 1 }
        ]
      }
    })

    // The drawing is hidden from assistive technology; the table is not.
    expect(wrapper.find('[data-testid="measure-bars-chart"]').attributes('aria-hidden')).toBe('true')
    const table = wrapper.find('[data-testid="measure-table"]')
    expect(table.find('caption').text()).toBe('By category')
    expect(table.findAll('th').map((th) => th.attributes('scope'))).toEqual(['row', 'row'])
    expect(rowsOf(wrapper)).toEqual(['Account and access|4', 'Registration|1'])
    // In the page from the start, hidden only from the eye. A closed
    // <details>, which React used, would take it out of the tree as well.
    expect(table.classes()).toContain('sr-only')
  })

  it('shows the table to a sighted reader on "Show as a table", a native button', async () => {
    // A <button type="button"> is what makes it reachable with Tab and
    // pressable with Enter or Space; jsdom does not turn a key into a click,
    // so the element is asserted and the click stands in for the key.
    const wrapper = mount(MeasureBars, {
      props: { label: 'By category', rows: [{ label: 'Other', value: 2 }] }
    })
    const toggle = wrapper.find('button')
    const table = wrapper.find('[data-testid="measure-table"]')

    expect(toggle.text()).toBe('Show as a table')
    expect(toggle.attributes('type')).toBe('button')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.attributes('aria-controls')).toBe(table.attributes('id'))

    await toggle.trigger('click')

    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(table.classes()).not.toContain('sr-only')

    await toggle.trigger('click')

    expect(table.classes()).toContain('sr-only')
  })
})
