// Node 25 exposes a method-less `localStorage`/`sessionStorage` global (it warns
// `--localstorage-file was provided without a valid path`) which shadows jsdom's.
// Anything reading storage at import time — @vue/devtools-kit, pulled in via
// pinia and vue-router — then dies with "getItem is not a function".
const installStorage = (name: 'localStorage' | 'sessionStorage') => {
  if (typeof (globalThis as never as Record<string, Storage>)[name]?.getItem === 'function') return

  const store = new Map<string, string>()
  const storage: Storage = {
    get length() {
      return store.size
    },
    key: (index: number) => [...store.keys()][index] ?? null,
    getItem: (key: string) => (store.has(String(key)) ? store.get(String(key))! : null),
    setItem: (key: string, value: string) => {
      store.set(String(key), String(value))
    },
    removeItem: (key: string) => {
      store.delete(String(key))
    },
    clear: () => {
      store.clear()
    },
  }
  Object.defineProperty(globalThis, name, { configurable: true, value: storage })
}

installStorage('localStorage')
installStorage('sessionStorage')
