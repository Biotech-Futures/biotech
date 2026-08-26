/**
 * Vuetify instance for the admin section.
 *
 * Loaded lazily from admin route components only — nothing outside src/admin/
 * may import this module, so Vuetify never lands in student-facing chunks.
 *
 * Colors mirror the BTF brand tokens in src/assets/main.css. The active theme
 * follows the app-wide dark mode toggle, which App.vue applies as
 * `data-theme="dark"` on <html> (persisted under the `biotech-theme`
 * localStorage key).
 *
 * Icons use the Font Awesome classes already loaded from the CDN in
 * index.html, matching the rest of the app.
 */
import { getCurrentInstance, type App } from 'vue'
import { createVuetify } from 'vuetify'
import { aliases, fa } from 'vuetify/iconsets/fa'
import 'vuetify/styles'

const currentThemeName = () =>
  document.documentElement.dataset.theme === 'dark' ? 'btfDark' : 'btfLight'

export const vuetify = createVuetify({
  icons: {
    defaultSet: 'fa',
    aliases,
    sets: { fa },
  },
  theme: {
    defaultTheme: currentThemeName(),
    themes: {
      btfLight: {
        dark: false,
        colors: {
          primary: '#017151', // --dark-green
          secondary: '#39687b', // --air-force-blue
          accent: '#5ea99e', // --mint-green
          background: '#f8f9fa', // --bg-light
          surface: '#ffffff', // --surface-elevated
          error: '#dc3545', // --danger
          warning: '#ffc107', // --warning
          info: '#17a2b8', // --info
          success: '#28a745', // --success
        },
      },
      btfDark: {
        dark: true,
        colors: {
          primary: '#017151',
          secondary: '#5ea99e',
          accent: '#5ea99e',
          background: '#0f1715', // --bg-light (dark)
          surface: '#1d2826', // --surface-elevated (dark)
          error: '#f87171',
          warning: '#fbbf24',
          info: '#60a5fa',
          success: '#28a745',
        },
      },
    },
  },
})

let installed = false

/** Install Vuetify on the running app exactly once (safe to call repeatedly). */
export function installVuetify(app: App) {
  if (installed) return
  installed = true
  app.use(vuetify)
  syncThemeWithApp()
}

/**
 * Call from the setup() of any admin root component (AdminLayout, or a page
 * rendered outside it) so Vuetify is installed before its children render.
 */
export function useAdminVuetify() {
  const instance = getCurrentInstance()
  if (instance) installVuetify(instance.appContext.app)
}

/** Keep Vuetify's theme in lock-step with the app-wide data-theme attribute. */
function syncThemeWithApp() {
  const apply = () => {
    vuetify.theme.global.name.value = currentThemeName()
  }
  apply()
  new MutationObserver(apply).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  })
}
