import { afterEach, describe, expect, it } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import LinkDialog from '@/components/admin/LinkDialog.vue'

let wrapper: VueWrapper | null = null

const open = async (props: Record<string, unknown> = {}) => {
  wrapper = mount(LinkDialog, {
    attachTo: document.body,
    props: { modelValue: false, ...props }
  })
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

const input = () => document.body.querySelector<HTMLInputElement>('.link-dialog__input')!
const button = (text: string) =>
  [...document.body.querySelectorAll<HTMLButtonElement>('button')].find((b) => b.textContent?.includes(text))
const type = (value: string) => {
  input().value = value
  input().dispatchEvent(new Event('input'))
}
const pressEnter = () => input().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('LinkDialog for an email button', () => {
  const buttonProps = { kind: 'button', placeholders: ['{{ registration_url }}'] }

  it("offers the email's link placeholders and adds a button with the chosen one", async () => {
    const dialog = await open(buttonProps)
    expect(document.body.textContent).toContain('Add a button')

    button('{{ registration_url }}')!.click()
    await flushPromises()
    expect(input().value).toBe('{{ registration_url }}')

    button('Add button')!.click()
    await flushPromises()
    expect(dialog.emitted('confirm')).toEqual([['{{ registration_url }}']])
    expect(dialog.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('explains a link it cannot use and stays open', async () => {
    const dialog = await open(buttonProps)
    type('register here')
    pressEnter()
    await flushPromises()

    expect(dialog.emitted('confirm')).toBeUndefined()
    expect(document.body.querySelector('.link-dialog__error')?.textContent).toContain('pick one of the links above')
  })

  it('starts from the current link when changing one, and saves it with Enter', async () => {
    const dialog = await open({ ...buttonProps, adding: false, initialLink: '{{ registration_url }}' })
    expect(document.body.textContent).toContain('Change the button link')
    expect(input().value).toBe('{{ registration_url }}')

    type('biotechfutures.org/symposium')
    pressEnter()
    await flushPromises()
    expect(dialog.emitted('confirm')).toEqual([['https://biotechfutures.org/symposium']])
  })
})

describe('LinkDialog for a text link', () => {
  it('adds a link, with nothing to remove yet', async () => {
    const dialog = await open()
    expect(document.body.textContent).toContain('Add a link')
    expect(button('Remove link')).toBeUndefined()

    type('support@biotechfutures.org')
    button('Add link')!.click()
    await flushPromises()
    expect(dialog.emitted('confirm')).toEqual([['mailto:support@biotechfutures.org']])
  })

  it('removes an existing link', async () => {
    const dialog = await open({ adding: false, initialLink: 'https://biotechfutures.org' })
    expect(document.body.textContent).toContain('Change the link')

    button('Remove link')!.click()
    await flushPromises()
    expect(dialog.emitted('remove')).toHaveLength(1)
    expect(dialog.emitted('confirm')).toBeUndefined()
  })

  it('takes a site path only where one works', async () => {
    const onSite = await open({ allowRelative: true })
    type('/events')
    pressEnter()
    await flushPromises()
    expect(onSite.emitted('confirm')).toEqual([['/events']])
    onSite.unmount()

    const inEmail = await open()
    type('/events')
    pressEnter()
    await flushPromises()
    expect(inEmail.emitted('confirm')).toBeUndefined()
  })
})
