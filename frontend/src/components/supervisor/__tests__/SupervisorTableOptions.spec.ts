import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SupervisorTableOptions from '../SupervisorTableOptions.vue'
import { printHtmlDocument } from '@/utils/consentDocument'
import { appSelectText, openAppSelect, pickAppSelect } from '@/__tests__/appSelect'

vi.mock('@/utils/consentDocument', () => ({ printHtmlDocument: vi.fn() }))

const rows = [
  { name: 'Ada "A" Lee', email: 'ada@example.com', pgEmail: 'pat@example.com' },
  { name: 'Ben <b>Ho</b>', email: 'ben@example.com', pgEmail: '' },
]

const mountOptions = (selectedRows: Record<string, unknown>[] = []) =>
  mount(SupervisorTableOptions, {
    props: {
      columns: [
        { key: 'name', label: 'Student' },
        { key: 'email', label: 'Email' },
      ],
      rows,
      pageRows: [rows[0]!],
      selectedRows,
      filename: 'students',
      emailKeys: ['email', 'pgEmail'],
    },
    global: { stubs: { teleport: true } },
  })

// jsdom's Blob has no text(), so it's read the way a browser page would.
const readBlob = (blob: Blob) =>
  new Promise<string>((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.readAsText(blob)
  })

const pick = (wrapper: ReturnType<typeof mountOptions>, label: string) =>
  pickAppSelect(wrapper, '.table-options__select', label)

describe('SupervisorTableOptions', () => {
  const writeText = vi.fn()

  beforeEach(() => {
    writeText.mockReset().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    vi.mocked(printHtmlDocument).mockReset()
  })

  afterEach(() => vi.unstubAllGlobals())

  it('lists each action under its heading, the ticked-row ones only once rows are ticked', async () => {
    const wrapper = mountOptions()
    const options = await openAppSelect(wrapper, '.table-options__select')

    expect(wrapper.findAll('.app-select__group').map((heading) => heading.text())).toEqual([
      'Export',
      'Clipboard',
      'View',
    ])
    const exportSelected = options.find((option) => option.textContent?.includes('Export selected (CSV)'))
    expect(exportSelected?.getAttribute('aria-disabled')).toBe('true')
  })

  it('does the action picked and goes back to "Select"', async () => {
    const wrapper = mountOptions()

    expect(appSelectText(wrapper, '.table-options__select')).toBe('Select')
    await pick(wrapper, 'Copy emails')

    // Students' and guardians' emails, each once, blanks left out.
    expect(writeText).toHaveBeenCalledWith('ada@example.com, pat@example.com, ben@example.com')
    expect(appSelectText(wrapper, '.table-options__select')).toBe('Select')
  })

  it('copies the table, or just the ticked rows, as tab-separated lines', async () => {
    const wrapper = mountOptions([rows[1]!])
    await pick(wrapper, 'Copy table')
    expect(writeText).toHaveBeenLastCalledWith(
      'Student\tEmail\nAda "A" Lee\tada@example.com\nBen <b>Ho</b>\tben@example.com',
    )
    await pick(wrapper, 'Copy selected rows')
    expect(writeText).toHaveBeenLastCalledWith('Student\tEmail\nBen <b>Ho</b>\tben@example.com')
  })

  describe('CSV exports', () => {
    let blobs: Blob[]
    let names: string[]

    beforeEach(() => {
      blobs = []
      names = []
      vi.stubGlobal('URL', {
        ...URL,
        createObjectURL: (blob: Blob) => {
          blobs.push(blob)
          return 'blob:students'
        },
        revokeObjectURL: vi.fn(),
      })
      vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download)
      })
    })

    afterEach(() => vi.restoreAllMocks())

    it('exports every matching row, quoting each cell', async () => {
      const wrapper = mountOptions()
      await pick(wrapper, 'Export all matching (CSV)')
      expect(names).toEqual(['students.csv'])
      expect(await readBlob(blobs[0]!)).toBe(
        'Student,Email\n"Ada ""A"" Lee","ada@example.com"\n"Ben <b>Ho</b>","ben@example.com"',
      )
    })

    it('exports this page, or the ticked rows, to their own files', async () => {
      const wrapper = mountOptions([rows[1]!])
      await pick(wrapper, 'Export this page (CSV)')
      await pick(wrapper, 'Export selected (CSV)')
      expect(names).toEqual(['students-page.csv', 'students-selected.csv'])
      expect(await readBlob(blobs[0]!)).toContain('ada@example.com')
      expect(await readBlob(blobs[0]!)).not.toContain('ben@example.com')
      expect(await readBlob(blobs[1]!)).toContain('ben@example.com')
      expect(await readBlob(blobs[1]!)).not.toContain('ada@example.com')
    })
  })

  it('prints the table with its text escaped', async () => {
    const wrapper = mountOptions()
    await pick(wrapper, 'Print table')
    expect(printHtmlDocument).toHaveBeenCalledTimes(1)
    const [title, html] = vi.mocked(printHtmlDocument).mock.calls[0]!
    expect(title).toBe('students')
    expect(html).toContain('<th>Student</th><th>Email</th>')
    expect(html).toContain('<td>Ada &quot;A&quot; Lee</td>')
    expect(html).toContain('<td>Ben &lt;b&gt;Ho&lt;/b&gt;</td>')
  })
})
