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

  it("draws an email's table with its own lines and padding", async () => {
    const wrapper = mount(RichEditor, { props: { emailMode: true }, attachTo: document.body })
    await flushPromises()
    await wrapper.findAll('.toolbar-btn').find((b) => b.text().trim() === 'Table')!.trigger('mousedown')
    const html = String(wrapper.emitted('update:modelValue')?.at(-1)?.[0] ?? '')
    expect(html).toContain('border-collapse: collapse')
    // Every cell, header or not, with a thin line and padding.
    expect(html).toMatch(/<th style="border: 1px solid [^"]+; padding: 6px 10px;"/)
    expect(html).toMatch(/<td style="border: 1px solid [^"]+; padding: 6px 10px;"/)
    wrapper.unmount()
  })
})
