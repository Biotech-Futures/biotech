import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ResourceUsageTrendChart from '@/components/analytics/ResourceUsageTrendChart.vue'
import { BTF_COLORS } from '@/constants/btfTheme'
import type { ResourceDailyUsage } from '@/types/analytics'

function rows(count: number): ResourceDailyUsage[] {
  return Array.from({ length: count }, (_, index) => ({
    resourceId: index + 1,
    name: `Resource ${String(index + 1).padStart(2, '0')}`,
    date: '2026-09-26',
    clicks: count - index,
    uniqueUsers: Math.max(1, count - index - 1),
  }))
}

describe('ResourceUsageTrendChart', () => {
  it('exhausts BTF colour and line-style combinations before fallback colours', async () => {
    const wrapper = mount(ResourceUsageTrendChart, { props: { rows: rows(37) } })
    const swatches = wrapper.findAll('.resource-trend-chip .resource-trend-swatch line')

    expect(swatches).toHaveLength(37)
    expect(swatches.slice(0, 6).map((swatch) => swatch.attributes('stroke'))).toEqual([
      BTF_COLORS.darkGreen,
      BTF_COLORS.teal,
      BTF_COLORS.airForceBlue,
      BTF_COLORS.mintGreen,
      BTF_COLORS.lightGreen,
      BTF_COLORS.yellow,
    ])
    expect(swatches[0]!.attributes('stroke-dasharray')).toBeUndefined()
    expect(swatches[1]!.attributes('stroke-dasharray')).toBe('10 6')
    expect(swatches[2]!.attributes('stroke-dasharray')).toBe('2 6')
    expect(swatches[3]!.attributes('stroke-dasharray')).toBe('10 5 2 5')
    expect(swatches[6]!.attributes('stroke')).toBe(BTF_COLORS.teal)
    expect(swatches[6]!.attributes('stroke-dasharray')).toBeUndefined()
    expect(swatches[35]!.attributes('stroke')).toBe(BTF_COLORS.lightGreen)
    expect(swatches[35]!.attributes('stroke-dasharray')).toBe('14 5 2 5 2 5')
    expect(swatches[36]!.attributes('stroke')).toBe('#8a5a9e')
    expect(swatches[36]!.attributes('stroke-dasharray')).toBeUndefined()

    const visibleLines = wrapper.findAll('polyline.resource-trend-line')
    expect(visibleLines).toHaveLength(6)
    expect(visibleLines[1]!.attributes('stroke')).toBe(BTF_COLORS.teal)
    expect(visibleLines[1]!.attributes('stroke-dasharray')).toBe('10 6')

    expect(wrapper.findAll('.resource-trend-x-axis').map((label) => label.text())).toEqual([
      '29 Aug',
      '5 Sept',
      '12 Sept',
      '19 Sept',
      '26 Sept',
    ])

    const readoutPosition = () => {
      const style = (wrapper.get('.resource-trend-readout').element as HTMLElement).style
      return {
        left: Number.parseFloat(style.left),
        top: Number.parseFloat(style.top),
      }
    }
    await wrapper.get('svg[role="img"]').trigger('mousemove', { clientX: 700, clientY: 100 })
    expect(wrapper.get('.resource-trend-readout-header').text()).toContain('Clicks')
    const rightHoverPosition = readoutPosition()
    expect(rightHoverPosition.top).toBe(112)
    expect(rightHoverPosition.left).toBeLessThanOrEqual(420)
    await wrapper.get('svg[role="img"]').trigger('mousemove', { clientX: 0, clientY: 100 })
    expect(readoutPosition().left).toBeGreaterThanOrEqual(0)
    await wrapper.get('svg[role="img"]').trigger('mousemove', { clientX: 550, clientY: 140 })
    const middleHoverPosition = readoutPosition()
    expect(rightHoverPosition.left).toBeGreaterThan(middleHoverPosition.left)
    expect(middleHoverPosition.top).toBe(152)
    expect(wrapper.findAll('.resource-trend-readout-row')).toHaveLength(6)
    expect(wrapper.findAll('.resource-trend-readout-row > .resource-trend-swatch')).toHaveLength(0)
    expect(wrapper.findAll('.resource-trend-readout-value .resource-trend-swatch')).toHaveLength(6)

    await wrapper.get('[aria-label="Resource trend period"]').setValue('365')
    const annualLabels = wrapper.findAll('.resource-trend-x-axis').map((label) => label.text())
    expect(annualLabels).toHaveLength(8)
    expect(annualLabels.at(-1)).toBe('26 Sept')
  })
})
