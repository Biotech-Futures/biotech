import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SupervisorTableOptions from '../SupervisorTableOptions.vue'
import { appSelectText, openAppSelect, pickAppSelect } from '@/__tests__/appSelect'

const mountOptions = (selectedRows: Record<string, unknown>[] = []) =>
  mount(SupervisorTableOptions, {
    props: {
      columns: [{ key: 'email', label: 'Email' }],
      rows: [{ email: 'ada@example.com' }, { email: 'ben@example.com' }],
      pageRows: [{ email: 'ada@example.com' }],
      selectedRows,
      filename: 'students',
      emailKeys: ['email']
    },
    global: { stubs: { teleport: true } }
  })

describe('SupervisorTableOptions', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists each action under its heading, the ticked-row ones only once rows are ticked', async () => {
    const wrapper = mountOptions()
    const options = await openAppSelect(wrapper, '.table-options__select')

    expect(wrapper.findAll('.app-select__group').map((heading) => heading.text())).toEqual([
      'Export',
      'Clipboard',
      'View'
    ])
    const exportSelected = options.find((option) => option.textContent?.includes('Export selected (CSV)'))
    expect(exportSelected?.getAttribute('aria-disabled')).toBe('true')
  })

  it('does the action picked and goes back to "Select"', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const wrapper = mountOptions()

    expect(appSelectText(wrapper, '.table-options__select')).toBe('Select')
    await pickAppSelect(wrapper, '.table-options__select', 'Copy emails')

    expect(writeText).toHaveBeenCalledWith('ada@example.com, ben@example.com')
    expect(appSelectText(wrapper, '.table-options__select')).toBe('Select')
  })
})
