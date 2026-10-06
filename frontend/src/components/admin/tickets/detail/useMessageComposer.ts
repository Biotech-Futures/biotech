import { nextTick, ref } from 'vue'

import { messageRefusedMessage } from './ticketDetailText'

// Both sides refuse more than this: backend MAX_BODY_LENGTH in
// apps/tickets/serializers.py. The two must agree.
export const MAX_BODY_LENGTH = 2000

// Matches the server's ALLOWED_EXTENSIONS (services/attachments.py) by hand;
// nothing ties them. The count, size and empty-file rules are the server's
// alone and come back as sentences the box shows (messageRefusedMessage).
export const ACCEPTED_FILES = '.pdf,.png,.jpg,.jpeg,.docx'

/**
 * The state the reply box and the internal-note box share: what was typed,
 * which files are picked, whether a send is in flight, and what went wrong.
 * One instance per box, so sending a reply does not mark the note box as
 * saving (T29: the React panel gave both boxes one pending flag).
 *
 * `deliver` resolves when the message is stored and rejects when it is not,
 * so a failed send keeps what was typed instead of throwing it away.
 */
export function useMessageComposer(deliver: (body: string, files: File[]) => Promise<unknown>) {
  const body = ref('')
  const files = ref<File[]>([])
  const isSending = ref(false)
  const error = ref('')

  const textarea = ref<HTMLTextAreaElement | null>(null)
  const fileInput = ref<HTMLInputElement | null>(null)
  const sendButton = ref<HTMLButtonElement | null>(null)

  function onFiles(event: Event) {
    files.value = Array.from((event.target as HTMLInputElement).files ?? [])
  }

  // Cleared only once the server has it. Clearing on click threw away a long
  // reply the moment anything went wrong (a rejected attachment, an expired
  // session) and left no trace on screen that it had gone.
  async function submit(): Promise<boolean> {
    // The double-submit guard. isSending is read live and set before the
    // first await, so a second click that lands before the button re-renders
    // as disabled stops here. The React boxes relied on `disabled` alone,
    // which reaches the DOM a render later.
    if (isSending.value || !body.value.trim()) return false
    isSending.value = true
    error.value = ''
    let sent = false
    try {
      await deliver(body.value.trim(), files.value)
      body.value = ''
      files.value = []
      // T14/T27: emptying `files` does not empty the input, which kept
      // showing the old file name while the next message went out with no
      // attachment. The input's own value has to go too.
      if (fileInput.value) fileInput.value.value = ''
      sent = true
    } catch (failure) {
      error.value = messageRefusedMessage(failure)
    } finally {
      isSending.value = false
    }
    // The Send button was disabled under the pointer while this ran, which
    // drops focus to the page. Put it back in the box, where the next thing
    // is typed, unless the agent has already moved on to something else.
    await nextTick()
    const active = document.activeElement
    if (!active || active === document.body || active === sendButton.value) {
      textarea.value?.focus()
    }
    return sent
  }

  return { body, files, isSending, error, textarea, fileInput, sendButton, onFiles, submit }
}
