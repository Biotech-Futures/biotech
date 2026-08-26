/**
 * TanStack Query (vue-query) setup for the admin section.
 *
 * Installed lazily from AdminLayout — same pattern as Vuetify — so the
 * library only loads with the admin chunks, never for students.
 *
 * Global defaults mirror the old admin SPA: no automatic refetching and no
 * retries. Individual queries opt back in (e.g. `refetchOnMount: true`)
 * where stale rows were a real problem, with a comment saying why.
 */
import { getCurrentInstance, type App } from 'vue'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      refetchOnMount: false,
      refetchInterval: false,
      retry: false,
    },
  },
})

let installed = false

/** Install vue-query on the running app exactly once (safe to call repeatedly). */
export function installVueQuery(app: App) {
  if (installed) return
  installed = true
  app.use(VueQueryPlugin, { queryClient })
}

/** Call from AdminLayout's setup() so every admin child can use useQuery. */
export function useAdminVueQuery() {
  const instance = getCurrentInstance()
  if (instance) installVueQuery(instance.appContext.app)
}
