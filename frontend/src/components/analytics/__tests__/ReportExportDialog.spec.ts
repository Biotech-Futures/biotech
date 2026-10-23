import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import ReportExportDialog from '@/components/analytics/ReportExportDialog.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

let wrapper: VueWrapper | null = null

function response(data: unknown) {
  return { ok: true, json: async () => ({ data }) }
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('ReportExportDialog', () => {
  it('opens one shared report chooser and downloads the selected backend report', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/countries/')) return response([{ id: 1, countryName: 'Australia' }])
      if (url.includes('/states/')) {
        return response([{ id: 2, stateName: 'NSW', countryName: 'Australia' }])
      }
      return {
        ok: true,
        blob: async () => new Blob(['period_start,period_end,login_count']),
        headers: new Headers({
          'Content-Disposition': 'attachment; filename="login_activity-2026-09-10.csv"',
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = vi.fn().mockReturnValue('blob:report')
      static revokeObjectURL = vi.fn()
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    wrapper = mount(ReportExportDialog)
    await wrapper.get('button.report-export-trigger').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="dialog"]').isVisible()).toBe(true)
    expect(wrapper.text()).toContain('Reports use live backend data')
    expect(wrapper.find('#report-export-group').exists()).toBe(true)

    await wrapper.get<HTMLSelectElement>('#report-export-type').setValue('login_activity')
    await wrapper.get<HTMLSelectElement>('#report-export-range').setValue('14d')
    expect(wrapper.find('#report-export-group').exists()).toBe(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('CSV download started.')
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/admin/analytics/reports/export/?report=login_activity&range=14d`,
      { credentials: 'include' },
    )
  })

  it('keeps the dialog open and explains an incomplete custom range', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([])))
    wrapper = mount(ReportExportDialog)
    await wrapper.get('button.report-export-trigger').trigger('click')
    await wrapper.get<HTMLSelectElement>('#report-export-type').setValue('announcement_delivery')
    await wrapper.get<HTMLSelectElement>('#report-export-range').setValue('custom')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.get('[role="alert"]').text()).toBe(
      'Start and end dates are required for a custom range.',
    )
    expect(wrapper.get('[role="dialog"]').isVisible()).toBe(true)
  })

  it('keeps keyboard focus inside the open dialog', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response([])))
    wrapper = mount(ReportExportDialog, { attachTo: document.body })
    await wrapper.get('button.report-export-trigger').trigger('click')
    await flushPromises()

    const dialog = wrapper.get('[role="dialog"]')
    const close = wrapper.get<HTMLButtonElement>('button.report-export-close')
    const download = wrapper.get<HTMLButtonElement>('button.report-export-download')

    download.element.focus()
    await dialog.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(close.element)

    close.element.focus()
    await dialog.trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(download.element)
  })

  it('announces a location-filter loading failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    wrapper = mount(ReportExportDialog)
    await wrapper.get('button.report-export-trigger').trigger('click')
    await flushPromises()

    expect(wrapper.get('.report-export-warning').attributes('role')).toBe('status')
  })
})
