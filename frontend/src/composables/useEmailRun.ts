import { onBeforeUnmount, watch } from 'vue'
import type { EmailRun, EmailRunState } from '@/utils/managementAPI'
import { plural } from '@/utils/string'

/** How often a page checks on a run while it sends. */
const CHECK_MS = 2000

/** A send is going or waiting its turn. */
export const isBusy = (state: EmailRunState | null | undefined) => Boolean(state?.sending || state?.queued)

/** "the A email", "the A and B emails", "the A, B and C emails". */
const emailsNamed = (names: string[]) =>
  names.length > 1
    ? `the ${names.slice(0, -1).join(', ')} and ${names[names.length - 1]} emails`
    : `the ${names[0]} email`

/** Said when a pressed send waits its turn, naming the emails ahead of it. */
export const queuedMessage = (ahead: string[]) =>
  ahead.length
    ? `Queued behind ${emailsNamed(ahead)}. It starts a few seconds after ${ahead.length === 1 ? 'that has' : 'those have'} finished.`
    : 'Queued. It starts in a few seconds.'

/** Beside the buttons while an email's sends wait their turn, naming the
 *  emails ahead of the first. */
export const queuedNote = (queued: number, ahead: string[]) => {
  const sends = queued === 1 ? 'Queued' : `${queued} sends queued`
  if (!ahead.length) return queued === 1 ? 'Queued, starts in a few seconds.' : `${sends}, each a few seconds apart.`
  const finished = ahead.length === 1 ? 'that has' : 'those have'
  return `${sends} behind ${emailsNamed(ahead)}, ${queued === 1 ? 'starts' : 'the first starts'} once ${finished} finished.`
}

/**
 * A bulk email's run sends on the server, so the page can be closed. While
 * ``state`` says it's sending or queued, this checks back every few seconds
 * (``refresh``), and once it's done, hands ``onFinished`` the finished run,
 * if this page saw it going.
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
    () => isBusy(state()),
    (busy, was) => {
      stop()
      if (busy) {
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
 *  can't be delivered come back to; for a group's one email, the rest of the
 *  group still gets it. */
export const deliveryNote = (sentFrom: string, toGroups = true) =>
  "Emails can take a few minutes to arrive. Any that can't be delivered, such as a mistyped address " +
  `or one a school's mail server refuses, come back to ${sentFrom}` +
  (toGroups ? ' and the rest of the group still gets it.' : '.')

/** What a page says once a run finishes, and whether it's an error: how
 *  many were emailed, then why it stopped short and how to retry. Always
 *  ends with where any that can't be delivered come back to. */
export function describeRun(run: EmailRun, wording: RunWording): { text: string; isError: boolean } {
  const sent = `Emailed ${plural(run.emailed, ...wording.emailed)}.`
  // An email to each supervisor isn't a group's.
  const note = wording.sentFrom ? ` ${deliveryNote(wording.sentFrom, !wording.failedWhole)}` : ''
  if (run.error) return { text: `${sent} ${run.error}${note}`, isError: true }
  if (run.failed) {
    const missed = wording.failedWhole
      ? `${plural(run.failed, wording.failed)} couldn't be emailed`
      : `${plural(run.failed, wording.failed)} ${run.failed === 1 ? "wasn't" : "weren't"} emailed in full`
    return {
      text: `${sent} ${missed}; press ${wording.button} to email only those it missed.${note}`,
      isError: true,
    }
  }
  if (run.due === 0 && wording.nobodyDue) return { text: `${wording.nobodyDue}${note}`, isError: false }
  return { text: `${sent}${note}`, isError: false }
}
