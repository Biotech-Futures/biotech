
export function getResourceIcon(type: string): string {
  const icons: Record<string, string> = {
    document: 'fas fa-file-alt',
    video: 'fas fa-video',
    link: 'fas fa-link',
    pdf: 'fas fa-file-pdf',
    article: 'fas fa-newspaper'
  }

  return icons[type] || 'fas fa-file'
}

/** A resource's icon in the tables that list them (the Resources page,
 *  Release Resources): by its kind, and a file's by its type. */
export function resourceFileIcon(resource: { kind?: string | null; file_mime_type?: string | null }): string {
  const mimeType = resource.file_mime_type?.toLowerCase() || ''
  if (resource.kind === 'page') return 'fas fa-globe'
  if (resource.kind === 'attachment') return 'fas fa-paperclip'
  if (mimeType.includes('pdf')) return 'fas fa-file-pdf'
  if (mimeType.startsWith('image/')) return 'fas fa-file-image'
  if (mimeType.startsWith('video/')) return 'fas fa-file-video'
  if (mimeType.startsWith('audio/')) return 'fas fa-file-audio'
  return 'fas fa-file-alt'
}
