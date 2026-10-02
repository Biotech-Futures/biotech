import { onBeforeUnmount, watch } from 'vue'
import type { EmailRun, EmailRunState } from '@/utils/managementAPI'
import { plural } from '@/utils/string'

/** How often a page checks on a run while it sends. */
const CHECK_MS = 2000

/**
 * A bulk email's run sends on the server, so the page can be closed. While
 * ``state`` says it's sending, this checks back every few seconds
 * (``refresh``), and once it stops, hands ``onFinished`` the finished run, if
 * this page saw it sending.
 */
export function useEmailRun(
  state: () => EmailRunState | null | undefined,
  refresh: () => Promise<unknown>,
  onFinished: (run: EmailRun) => void
) {
  let timer: ReturnType<typeof setInterval> | null = null
  const stop = () => {
    if (timer !== null) clearInterval(timer)
    timer = null
  }
  watch(
    () => Boolean(state()?.sending),
    (sending, was) => {
      stop()
      if (sending) {
        timer = setInterval(() => void refresh(), CHECK_MS)
      } else if (was) {
        const run = state()?.run
        if (run) onFinished(run)
      }
    }
  )
  onBeforeUnmount(stop)
}

/** How a page words a finished run. */
export interface RunWording {
  /** Who was emailed: ['person', 'people'], or ['supervisor']. */
  emailed: [string, string?]
  /** What a failure counts: 'team', 'group' or 'supervisor'. */
  failed: string
  /** Each failure is one email ("couldn't be emailed"), not a team some of
   *  whose members were missed ("wasn't emailed in full"). */
  failedWhole?: boolean
  /** The button that retries, e.g. "Email Groups". */
  button: string
  /** Said instead of "Emailed 0 people." when nobody was due the email. */
  nobodyDue?: string
  /** The address the emails went out from, for where bounces come back. */
  sentFrom?: string
}

/** How long a finished run's message stays: it has more to read. */
export const RUN_MESSAGE_MS = 15000

/** Once emails have gone: they're not all there yet, and where any that
 *  can't be delivered come back to. */
export const deliveryNote = (sentFrom: string) =>
  "Emails can take a few minutes to arrive. Any that can't be delivered, such as a mistyped address " +
  `or one a school's mail server refuses, come back to ${sentFrom}.`

/** What a page says once a run finishes, and whether it's an error: how
 *  many were emailed, then why it stopped short and how to retry. */
export function describeRun(run: EmailRun, wording: RunWording): { text: string; isError: boolean } {
  const sent = `Emailed ${plural(run.emailed, ...wording.emailed)}.`
  if (run.error) return { text: `${sent} ${run.error}`, isError: true }
  if (run.failed) {
    const missed = wording.failedWhole
      ? `${plural(run.failed, wording.failed)} couldn't be emailed`
      : `${plural(run.failed, wording.failed)} ${run.failed === 1 ? "wasn't" : "weren't"} emailed in full`
    return { text: `${sent} ${missed}; press ${wording.button} again to retry.`, isError: true }
  }
  if (run.due === 0 && wording.nobodyDue) return { text: wording.nobodyDue, isError: false }
  const note = run.emailed > 0 && wording.sentFrom ? ` ${deliveryNote(wording.sentFrom)}` : ''
  return { text: `${sent}${note}`, isError: false }
}
