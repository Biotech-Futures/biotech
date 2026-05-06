// 定义一个常量的映射表，可以理解为一个字典
// key是资源类型，字符串形式，比如文件document，视频video等
// value是对应图标的class
// 例如页面也可以写：<i :class="getResourceIcon(resource.type)"></i>
// 如果 resource.type === 'video'，那渲染出来就是：<i class="fas fa-video"></i>
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