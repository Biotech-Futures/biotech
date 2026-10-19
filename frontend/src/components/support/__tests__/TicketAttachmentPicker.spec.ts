import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import TicketAttachmentPicker from '../TicketAttachmentPicker.vue'
// The stylesheet is read as text: jsdom applies no scoped-SFC styles.
import SOURCE from '../TicketAttachmentPicker.vue?raw'

function file(name: string, size = 1024) {
  const f = new File(['x'.repeat(16)], name, { type: 'application/pdf' })
  Object.defineProperty(f, 'size', { value: size })
  return f
}

async function pick(wrapper: ReturnType<typeof mount>, files: File[]) {
  const input = wrapper.get('input[type="file"]')
  Object.defineProperty(input.element, 'files', { value: files, configurable: true })
  await input.trigger('change')
}

/**
 * The whole component had no tests. Its one non-obvious behaviour is the cap:
 * a sixth file must be refused OUT LOUD, because a silently dropped file is a
 * student believing they sent a screenshot that support never received.
 */
describe('TicketAttachmentPicker', () => {
  it('says so when the cap cuts files, instead of dropping them silently', async () => {
    const wrapper = mount(TicketAttachmentPicker, {
      props: { modelValue: [] },
    })

    await pick(wrapper, [0, 1, 2, 3, 4, 5].map((i) => file(`f${i}.pdf`)))

    expect(wrapper.text()).toContain(
      'Unable to upload: you can attach up to 5 files to one message.'
    )
  })

  it('keeps exactly five and not the sixth', async () => {
    const wrapper = mount(TicketAttachmentPicker, {
      props: { modelValue: [] },
    })

    await pick(wrapper, [0, 1, 2, 3, 4, 5].map((i) => file(`f${i}.pdf`)))

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect((emitted![0][0] as File[]).length).toBe(5)
  })

  it('rejects an oversized file by name, and says how big it is', async () => {
    const wrapper = mount(TicketAttachmentPicker, {
      props: { modelValue: [] },
    })

    await pick(wrapper, [file('huge.pdf', 11 * 1024 * 1024)])

    // The designer's sentence (D2-06), after the client asked for refusals a
    // Year 9 student cannot misread (C-23).
    expect(wrapper.text()).toContain('Unable to upload: huge.pdf is larger than 10 MB (it is 11 MB).')
  })

  it('never says a file over the limit is 10 MB', async () => {
    // Rounded to the nearest tenth, a file 40 KB over the limit would read
    // "larger than 10 MB (it is 10 MB)". Rounded up, it cannot.
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })

    await pick(wrapper, [file('just-over.pdf', 10 * 1024 * 1024 + 40 * 1024)])

    expect(wrapper.text()).toContain('just-over.pdf is larger than 10 MB (it is 10.1 MB).')
  })
})

/**
 * The limits are said before anything is chosen, and the count joins them
 * once something is: the client asked at the 8 October meeting for the
 * number to be shown beside the size ("Max file size ten megabytes, max
 * number...", C-23), and the designer drew it as "Up to 5 files, 10 MB each
 * (...) · 2 of 5 added" (D2-05).
 */
describe('the hint beside the button', () => {
  it('names both limits and the four types', () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })
    expect(wrapper.get('.attach__hint').text()).toBe('Up to 5 files, 10 MB each (PDF, PNG, JPG, DOCX)')
  })

  it('adds how many are chosen once there are some', () => {
    const wrapper = mount(TicketAttachmentPicker, {
      props: { modelValue: [file('a.pdf'), file('b.png')] },
    })
    expect(wrapper.get('.attach__hint').text()).toBe(
      'Up to 5 files, 10 MB each (PDF, PNG, JPG, DOCX) · 2 of 5 added'
    )
  })
})

/**
 * Keyboard focus lands on the file input, a transparent 1px box whose own
 * ring cannot be seen. The designer tabbed to Attach files in both themes and
 * saw nothing move (DT-02, checklist R4). The button draws the ring instead,
 * and this holds the rule that does it to the source: jsdom draws no focus.
 */
describe('keyboard focus on Attach files', () => {
  const style = (/<style scoped>([\s\S]*?)<\/style>/.exec(SOURCE) as RegExpExecArray)[1]!
    .replace(/\/\*[\s\S]*?\*\//g, '')

  it('rings the button while its hidden input has keyboard focus', () => {
    const rule = /\.attach__button:has\(\.attach__input:focus-visible\)\s*\{([^}]*)\}/.exec(style)
    expect(rule).not.toBeNull()
    expect(rule![1]).toMatch(/outline:\s*2px solid var\(--attach-focus\)/)
  })

  it('gives the ring a colour in both themes', () => {
    expect(style).toMatch(/\.attach\s*\{[^}]*--attach-focus:\s*var\(--dark-green\)/)
    expect(style).toMatch(/:root\[data-theme='dark'\] \.attach\s*\{[^}]*--attach-focus:\s*#6dbfb1/)
  })
})

/**
 * p48 asks for "Drag and drop files here or click to attach". The button half
 * shipped and the drop half did not, which is easy to miss because the field
 * still works — it just does nothing at all when a file is dragged onto it,
 * and the page's own hint never said it should.
 *
 * Since the second redesign round only the reply box says so: the designer
 * shortened the new-ticket form's hint to the limits and left the reply box's
 * sentence in place. The drop zone itself works in both.
 */
describe('the drop zone', () => {
  async function drop(wrapper: ReturnType<typeof mount>, files: File[]) {
    await wrapper.trigger('drop', { dataTransfer: { files } })
  }

  it('tells the reader they can drag files onto it, where it is asked to', () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [], dropHint: true } })
    expect(wrapper.get('.attach__hint').text()).toBe(
      'Drag and drop files here or click to attach. Up to 5 files, 10 MB each (PDF, PNG, JPG, DOCX)'
    )
  })

  it('leaves the sentence out of the new-ticket form', () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })
    expect(wrapper.text()).not.toContain('Drag and drop')
  })

  it('accepts a dropped file the same way as a picked one', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })

    await drop(wrapper, [file('dropped.pdf')])

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect((emitted![0][0] as File[]).map((f) => f.name)).toEqual(['dropped.pdf'])
  })

  it('applies the size limit to a dropped file too', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })

    await drop(wrapper, [file('huge.pdf', 11 * 1024 * 1024)])

    expect(wrapper.text()).toContain('Unable to upload: huge.pdf is larger than 10 MB (it is 11 MB).')
  })

  it('refuses a type the accept attribute cannot police', async () => {
    // The reason this test exists. `accept` filters the operating system's
    // file dialog and has no effect on a drop, so adding a drop zone without
    // a type check would quietly widen what the form takes.
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })

    await drop(wrapper, [file('payload.exe')])

    expect(wrapper.text()).toContain('Unable to upload: payload.exe is not a PDF, PNG, JPG or DOCX.')
    const emitted = wrapper.emitted('update:modelValue')
    expect((emitted![0][0] as File[]).length).toBe(0)
  })

  it('takes the good files out of a mixed drop', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: [] } })

    await drop(wrapper, [file('notes.docx'), file('payload.exe'), file('shot.png')])

    const emitted = wrapper.emitted('update:modelValue')
    expect((emitted![0][0] as File[]).map((f) => f.name)).toEqual([
      'notes.docx',
      'shot.png',
    ])
  })
})

/**
 * A wrong file could only be removed, never swapped for the right one, and on
 * the support side not even removed (2026-10-07 testing, item 8). Replacing
 * works row by row and goes through the same checks as a new file.
 */
describe('replacing a picked file', () => {
  const picked = () => [file('first.pdf'), file('wrong.pdf'), file('third.pdf')]

  async function replace(wrapper: ReturnType<typeof mount>, name: string, replacement: File) {
    await wrapper.get(`button[aria-label="Replace ${name}"]`).trigger('click')
    const input = wrapper.findAll('input[type="file"]')[1]!
    Object.defineProperty(input.element, 'files', { value: [replacement], configurable: true })
    await input.trigger('change')
  }

  const names = (wrapper: ReturnType<typeof mount>) =>
    (wrapper.emitted('update:modelValue')?.at(-1)?.[0] as File[] | undefined)?.map((f) => f.name)

  it('opens a picker for one file when Replace is pressed', async () => {
    const opened: HTMLInputElement[] = []
    const click = vi
      .spyOn(HTMLInputElement.prototype, 'click')
      .mockImplementation(function (this: HTMLInputElement) {
        opened.push(this)
      })
    try {
      const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: picked() } })

      await wrapper.get('button[aria-label="Replace wrong.pdf"]').trigger('click')

      expect(opened).toHaveLength(1)
      expect(opened[0]!.multiple).toBe(false)
      expect(opened[0]).toBe(wrapper.findAll('input[type="file"]')[1]!.element)
    } finally {
      click.mockRestore()
    }
  })

  it('puts the new file in the old one’s place and leaves the others alone', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: picked() } })

    await replace(wrapper, 'wrong.pdf', file('right.pdf'))

    expect(names(wrapper)).toEqual(['first.pdf', 'right.pdf', 'third.pdf'])
  })

  it('refuses a replacement of the wrong type and keeps the original', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: picked() } })

    await replace(wrapper, 'wrong.pdf', file('setup.exe'))

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('Unable to upload: setup.exe is not a PDF, PNG, JPG or DOCX.')
  })

  it('refuses an oversized replacement and keeps the original', async () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: picked() } })

    await replace(wrapper, 'wrong.pdf', file('huge.pdf', 11 * 1024 * 1024))

    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    expect(wrapper.text()).toContain('Unable to upload: huge.pdf is larger than 10 MB (it is 11 MB).')
  })

  it('keeps its own picker out of the tab order, behind the named buttons', () => {
    const wrapper = mount(TicketAttachmentPicker, { props: { modelValue: picked() } })
    const input = wrapper.findAll('input[type="file"]')[1]!

    expect(input.attributes('tabindex')).toBe('-1')
    expect(input.attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('button').map((b) => b.attributes('aria-label'))).toEqual([
      'Replace first.pdf',
      'Remove first.pdf',
      'Replace wrong.pdf',
      'Remove wrong.pdf',
      'Replace third.pdf',
      'Remove third.pdf'
    ])
  })
})
