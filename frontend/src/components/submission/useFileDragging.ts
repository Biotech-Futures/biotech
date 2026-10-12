import { onBeforeUnmount, onMounted, ref } from 'vue'

/** Whether a file is being dragged anywhere over the window; previews let drops through meanwhile. */
export function useFileDragging(onDragEnd?: () => void) {
  const isDraggingFile = ref(false)

  function onEnter(event: DragEvent) {
    if (event.dataTransfer?.types?.includes('Files')) isDraggingFile.value = true
  }

  function onEnd(event: DragEvent) {
    // A dragleave with no related target means the file left the window.
    if (event.type === 'dragleave' && event.relatedTarget) return
    isDraggingFile.value = false
    onDragEnd?.()
  }

  onMounted(() => {
    window.addEventListener('dragenter', onEnter)
    window.addEventListener('dragleave', onEnd)
    window.addEventListener('dragend', onEnd)
    window.addEventListener('drop', onEnd)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('dragenter', onEnter)
    window.removeEventListener('dragleave', onEnd)
    window.removeEventListener('dragend', onEnd)
    window.removeEventListener('drop', onEnd)
  })

  return isDraggingFile
}
