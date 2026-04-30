import bg1 from '@/assets/dashboard_bg/dashboard_bg_1.jpg'
import bg2 from '@/assets/dashboard_bg/dashboard_bg_2.jpg'
import bg3 from '@/assets/dashboard_bg/dashboard_bg_3.jpg'
import bg4 from '@/assets/dashboard_bg/dashboard_bg_4.jpg'

export const DASHBOARD_BACKGROUND_OPTIONS = [
  {
    key: 'dashboard-bg-1',
    label: 'Background 1',
    image: bg1
  },
  {
    key: 'dashboard-bg-2',
    label: 'Background 2',
    image: bg2
  },
  {
    key: 'dashboard-bg-3',
    label: 'Background 3',
    image: bg3
  },
  {
    key: 'dashboard-bg-4',
    label: 'Background 4',
    image: bg4
  }
] as const

export const DASHBOARD_DEFAULT_BACKGROUND_KEY = DASHBOARD_BACKGROUND_OPTIONS[0].key