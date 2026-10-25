/**
 * Admin > Users > Import Students and Import Mentors: every address in the
 * file checked once it's chosen, before Import (POST user/import-check/).
 * A row's problems refuse it, as importing would; its warnings don't. New
 * addresses are looked up in the background first, and their progress
 * followed (GET user/import-check/<jobId>/), so a mailbox that doesn't exist
 * is warned about too.
 */
import { reactive } from 'vue'
import { adminGet, adminPost } from './adminAPI'
import { logApiError } from './apiError'

export type ImportCheckKind = 'students' | 'mentors'

export interface ImportCheckRow {
  row: number
  email: string
  firstName: string
  lastName: string
  guardianEmail?: string
  supervisorEmail?: string
  supervisorFirstName?: string
  supervisorLastName?: string
}

export interface ImportRowWarning {
  field: string
  message: string
}

export interface ImportRowCheck {
  row: number
  problems: string[]
  warnings: ImportRowWarning[]
}

interface CheckAnswer {
  results: ImportRowCheck[]
  lookups: { jobId: string; status: string; total: number; done: number } | null
}

interface LookupProgress {
  status: string
  total: number
  done: number
  errors?: number
}

// The longest a file's lookups are followed before importing goes on without them.
const MOST_MS = 10 * 60 * 1000

export const checkImportRows = (kind: ImportCheckKind, rows: ImportCheckRow[], lookup: boolean) =>
  adminPost<CheckAnswer>('/user/import-check/', { kind, rows, lookup })

export const importCheckProgress = (jobId: string) =>
  adminGet<LookupProgress>(`/user/import-check/${encodeURIComponent(jobId)}/`)

export function useImportEmailCheck(kind: ImportCheckKind, options: { pollMs?: number } = {}) {
  const pollMs = options.pollMs ?? 1500
  const state = reactive({ checking: false, done: 0, total: 0, note: '' })
  // Each check's number: a newer file's (or a closed sheet) ends an older one.
  let current = 0
  const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

  /** Whether the lookups finished; how many couldn't be done goes in the note. */
  const follow = async (jobId: string, mine: number): Promise<boolean> => {
    const deadline = Date.now() + MOST_MS
    while (Date.now() < deadline) {
      await wait(pollMs)
      if (mine !== current) return false
      let progress: LookupProgress
      try {
        progress = await importCheckProgress(jobId)
      } catch {
        return false
      }
      if (mine !== current) return false
      Object.assign(state, { done: progress.done, total: progress.total })
      if (progress.status === 'done') {
        if (progress.errors) {
          state.note = `${progress.errors} email${progress.errors === 1 ? '' : 's'} couldn't be checked.`
        }
        return true
      }
      if (progress.status !== 'queued' && progress.status !== 'running') return false
    }
    return false
  }

  /** Each row's check, by its row number; null when there's none (a newer
   *  check took over, or it couldn't be done: the note says so). */
  const check = async (rows: ImportCheckRow[]): Promise<Map<number, ImportRowCheck> | null> => {
    const mine = ++current
    Object.assign(state, { checking: true, done: 0, total: 0, note: '' })
    try {
      if (!rows.length) return new Map()
      let answer = await checkImportRows(kind, rows, true)
      if (mine !== current) return null
      if (answer.lookups) {
        Object.assign(state, { done: answer.lookups.done, total: answer.lookups.total })
        const finished = await follow(answer.lookups.jobId, mine)
        if (mine !== current) return null
        if (!finished) state.note = "Some emails couldn't be checked for whether they exist."
        answer = await checkImportRows(kind, rows, false)
        if (mine !== current) return null
      }
      return new Map(answer.results.map((result) => [result.row, result]))
    } catch (error) {
      if (mine !== current) return null
      logApiError('admin.import.email-check', error)
      state.note = "The emails couldn't be checked. You can still import."
      return null
    } finally {
      if (mine === current) state.checking = false
    }
  }

  const cancel = () => {
    current += 1
    Object.assign(state, { checking: false, done: 0, total: 0, note: '' })
  }

  return { state, check, cancel }
}

/** Rows ``results`` refuse move to ``invalid`` (with their problems as the
 *  reason); the rest stay, with their warnings by row number. */
export function applyImportCheck<Row extends { rowNumber: number; email: string }>(
  rows: Row[],
  invalid: Array<{ rowNumber: number; email: string; reason: string }>,
  results: Map<number, ImportRowCheck>,
) {
  const kept: Row[] = []
  const refused = [...invalid]
  const warnings = new Map<number, ImportRowWarning[]>()
  for (const row of rows) {
    const result = results.get(row.rowNumber)
    if (result?.problems.length) {
      refused.push({ rowNumber: row.rowNumber, email: row.email, reason: result.problems.join(' ') })
      continue
    }
    kept.push(row)
    if (result?.warnings.length) warnings.set(row.rowNumber, result.warnings)
  }
  refused.sort((a, b) => a.rowNumber - b.rowNumber)
  return { valid: kept, invalid: refused, warnings }
}
