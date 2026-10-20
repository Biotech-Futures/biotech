// Picking from an AppSelect in a spec, as a click on its box and then on a
// choice. Its list is drawn over the page (in document.body), or in place
// when a spec stubs Teleport, so both are searched.
import { flushPromises } from '@vue/test-utils'

type Findable = { find: (selector: string) => { exists: () => boolean; element: Element } }

const boxOf = (root: Findable, selector: string): HTMLElement => {
  const found = root.find(selector)
  if (!found.exists()) throw new Error(`No dropdown at ${selector}`)
  const element = found.element as HTMLElement
  const box = element.closest('.app-select') ?? element.querySelector('.app-select')
  if (!box) throw new Error(`${selector} is not an AppSelect`)
  return box as HTMLElement
}

/** Its choices, open, as the labels shown. */
export async function openAppSelect(root: Findable, selector: string): Promise<HTMLElement[]> {
  const box = boxOf(root, selector)
  const field = box.querySelector('input[role="combobox"]')
  // A click on the box toggles it, so only when it isn't open already (as
  // after typing in it).
  if (field?.getAttribute('aria-expanded') !== 'true') {
    box.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
    await flushPromises()
  }
  const listId = field?.getAttribute('aria-controls') ?? ''
  // Over the page, or in place within a spec's own (detached) tree.
  let top: HTMLElement = box
  while (top.parentElement) top = top.parentElement
  const list = document.getElementById(listId) ?? top.querySelector(`[id="${listId}"]`)
  return list ? Array.from(list.querySelectorAll<HTMLElement>('[role="option"]')) : []
}

/** The labels of its choices, opening it. */
export async function appSelectLabels(root: Findable, selector: string): Promise<string[]> {
  const options = await openAppSelect(root, selector)
  return options.map((option) => option.querySelector('.app-select__label')?.textContent?.trim() ?? '')
}

/** Picks the choice labelled `label`. */
export async function pickAppSelect(root: Findable, selector: string, label: string): Promise<void> {
  const options = await openAppSelect(root, selector)
  const option = options.find(
    (candidate) => candidate.querySelector('.app-select__label')?.textContent?.trim() === label
  )
  if (!option) {
    const labels = options.map((candidate) => candidate.querySelector('.app-select__label')?.textContent?.trim())
    throw new Error(`No choice "${label}" in ${selector}: ${labels.join(', ')}`)
  }
  option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
  await flushPromises()
}

/** What its box shows: the chosen label, as a select's shown text. */
export function appSelectText(root: Findable, selector: string): string {
  const input = boxOf(root, selector).querySelector<HTMLInputElement>('input[role="combobox"]')
  return input?.value ?? ''
}
