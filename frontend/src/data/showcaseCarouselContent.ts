export interface ShowcaseCarouselItem {
  id: string
  title: string
  summary: string
  image: string
  link: string
}

export const showcaseCarouselContent: ShowcaseCarouselItem[] = [
  {
    id: 'local-1',
    title: 'BIOTech innovation in modern research spaces',
    summary: 'Explore how research environments, instrumentation, and data systems support scalable BIOTech work.',
    image: 'https://images.unsplash.com/photo-1576086213369-97a306d36557?auto=format&fit=crop&w=1600&q=80',
    link: '/resources'
  },
  {
    id: 'local-2',
    title: 'Clinical and molecular workflows',
    summary: 'From microscopy to analytics dashboards, connected workflows help teams move faster with better visibility.',
    image: 'https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?auto=format&fit=crop&w=1600&q=80',
    link: '/announcements'
  },
  {
    id: 'local-3',
    title: 'Life science collaboration and platform operations',
    summary: 'BIOTech systems often combine research tools, data pipelines, and operational platforms in one ecosystem.',
    image: 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1600&q=80',
    link: '/groups'
  }
]
