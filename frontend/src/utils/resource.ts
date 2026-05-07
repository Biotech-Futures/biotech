
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
