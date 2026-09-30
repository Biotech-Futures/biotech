import { ref, type Ref } from 'vue'
import { apiErrorFromUnknown } from '@/utils/apiError'

/** Grow a preview's frame to the whole email, so only the dialog's box scrolls. */
export function fitPreview(event: Event) {
  const frame = event.target as HTMLIFrameElement
  const page = frame.contentDocument?.documentElement
  if (page) frame.style.height = `${page.scrollHeight}px`
}

/**
 * An email page's Preview: ``openPreview`` fetches the email as it would go
 * out and shows it in ``preview``; a failure goes in ``error``.
 * ``loadingPreview`` is which email is loading, the ``key`` it was opened
 * with, or ``false`` when none is. A page with one email opens it with
 * ``openPreview()`` and reads ``loadingPreview`` as true or false.
 */
export function useEmailPreview<P, K extends string = never>(
  fetchPreview: (key: K) => Promise<P>,
  error: Ref<string>
) {
  const preview = ref(null) as Ref<P | null>
  const loadingPreview = ref(false) as Ref<K | boolean>

  const openPreview = async (key?: K) => {
    error.value = ''
    loadingPreview.value = key ?? true
    try {
      // A page with one email never passes a key, and its fetch takes none.
      preview.value = await fetchPreview(key as K)
    } catch (err) {
      error.value = apiErrorFromUnknown(err).message
    } finally {
      loadingPreview.value = false
    }
  }

  return { preview, loadingPreview, openPreview, fitPreview }
}
