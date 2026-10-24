import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchState = vi.fn()
vi.mock('@/utils/managementAPI', () => ({
  fetchSupervisorResultsState: (...args: unknown[]) => fetchState(...args),
}))

// The composable keeps its state at module level, so each test loads it fresh.
const load = async () => import('@/composables/useSupervisorResults')

beforeEach(() => {
  vi.resetModules()
  fetchState.mockReset()
})

describe('useSupervisorResults', () => {
  it('stays hidden until something is released', async () => {
    fetchState.mockResolvedValue({ marks_released: false, certificates_released: false })
    const { loadSupervisorResults, useSupervisorResults } = await load()
    expect(await loadSupervisorResults()).toBe(false)
    expect(useSupervisorResults().shown.value).toBe(false)
  })

  it('opens once marks or certificates are released', async () => {
    fetchState.mockResolvedValue({ marks_released: false, certificates_released: true })
    const { loadSupervisorResults, useSupervisorResults } = await load()
    expect(await loadSupervisorResults()).toBe(true)
    expect(useSupervisorResults().shown.value).toBe(true)
  })

  it('asks the server once, unless forced', async () => {
    fetchState.mockResolvedValue({ marks_released: true, certificates_released: false })
    const { loadSupervisorResults } = await load()
    await Promise.all([loadSupervisorResults(), loadSupervisorResults()])
    expect(fetchState).toHaveBeenCalledTimes(1)
    await loadSupervisorResults(true)
    expect(fetchState).toHaveBeenCalledTimes(2)
  })

  it('keeps what it knew when the server is unreachable, and asks again next time', async () => {
    const { loadSupervisorResults, useSupervisorResults } = await load()
    fetchState.mockResolvedValueOnce({ marks_released: true, certificates_released: false })
    await loadSupervisorResults()
    fetchState.mockRejectedValueOnce(new Error('offline'))
    expect(await loadSupervisorResults(true)).toBe(true)
    expect(useSupervisorResults().shown.value).toBe(true)
    fetchState.mockResolvedValueOnce({ marks_released: false, certificates_released: false })
    await loadSupervisorResults()
    expect(fetchState).toHaveBeenCalledTimes(3)
  })
})
