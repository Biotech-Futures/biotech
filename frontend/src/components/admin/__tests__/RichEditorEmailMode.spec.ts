import { describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import RichEditor from '@/components/admin/RichEditor.vue'

const toolbarLabels = async (props: Record<string, unknown>) => {
  const wrapper = mount(RichEditor, { props, attachTo: document.body })
  await flushPromises()
  const labels = wrapper.findAll('.toolbar-btn').map((b) => b.text().trim())
  wrapper.unmount()
  return labels
}

describe('RichEditor in email mode', () => {
  it('offers Table but not Image or File, which an email would lose', async () => {
    const labels = await toolbarLabels({ emailMode: true })
    expect(labels).toContain('Table')
    expect(labels).not.toContain('Image')
    expect(labels).not.toContain('File')
  })

  it('offers all three elsewhere', async () => {
    const labels = await toolbarLabels({})
    expect(labels).toEqual(expect.arrayContaining(['Image', 'File', 'Table']))
  })

  it('offers text colour, size and gap in email mode only', async () => {
    const tools = async (props: Record<string, unknown>) => {
      const wrapper = mount(RichEditor, { props, attachTo: document.body })
      await flushPromises()
      const found = ['text-colour', 'text-size', 'text-gap'].filter((name) => wrapper.find(`[data-test="${name}"]`).exists())
      wrapper.unmount()
      return found
    }
    expect(await tools({ emailMode: true })).toEqual(['text-colour', 'text-size', 'text-gap'])
    expect(await tools({})).toEqual([])
  })

  it('highlights the gap below the paragraph, even one not on offer', async () => {
    const gapNow = async (modelValue: string) => {
      const wrapper = mount(RichEditor, { props: { emailMode: true, modelValue }, attachTo: document.body })
      await flushPromises()
      await wrapper.find('[data-test="text-gap"]').trigger('mousedown')
      const now = wrapper.find('[data-test="gap-now"]')
      const active = wrapper.findAll('.dropdown-item.active').map((item) => item.text().trim())
      wrapper.unmount()
      return { now: now.exists() ? now.text().trim() : null, active }
    }
    // The cursor starts in the first paragraph.
    expect(await gapNow('<p style="margin:0 0 24px 0">One</p><p>Two</p>')).toEqual({
      now: null,
      active: ['Large gap (24px)']
    })
    expect((await gapNow('<p style="margin:0 0 16px 0">One</p><p>Two</p>')).now).toBe('Now: 16px')
    expect((await gapNow('<p>One</p><p>Two</p>')).now).toBe('Now: default')
  })

  it("shows a template's coloured and sized text as written", async () => {
    const wrapper = mount(RichEditor, {
      props: {
        emailMode: true,
        modelValue: '<p style="color:#6d7a72; font-size:14px">Hi <span style="color:#307054">Pat</span>,</p>'
      },
      attachTo: document.body
    })
    await flushPromises()
    const p = wrapper.find('.ProseMirror p').element as HTMLElement
    expect(p.style.color).toBe('rgb(109, 122, 114)')
    expect(p.style.fontSize).toBe('14px')
    expect((wrapper.find('.ProseMirror p span').element as HTMLElement).style.color).toBe('rgb(48, 112, 84)')
    wrapper.unmount()
  })

  it("draws an email's table with its own lines and padding", async () => {
    const wrapper = mount(RichEditor, { props: { emailMode: true }, attachTo: document.body })
    await flushPromises()
    await wrapper.findAll('.toolbar-btn').find((b) => b.text().trim() === 'Table')!.trigger('mousedown')
    const html = String(wrapper.emitted('update:modelValue')?.at(-1)?.[0] ?? '')
    expect(html).toContain('border-collapse: collapse')
    // Every cell, header or not, with a thin line and padding.
    expect(html).toMatch(/<th[^>]* style="border: 1px solid [^"]+; padding: 6px 10px;"/)
    expect(html).toMatch(/<td[^>]* style="border: 1px solid [^"]+; padding: 6px 10px;"/)
    wrapper.unmount()
  })
})
