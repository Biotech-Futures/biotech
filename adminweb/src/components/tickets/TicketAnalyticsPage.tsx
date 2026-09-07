// Out of the route file for the same reason as TicketQueuePage and
// AdminHomePage: a route file that exports anything but its Route turns
// off autoCodeSplitting for that route, and the components that did it
// cost the main chunk 170 kB between them. Its test imports it from here.
import { useState } from "react";
import { isAxiosError } from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MeasureBars } from "@/components/tickets/MeasureBars";
import { wasRefused } from "@/lib/queryError";
import { useAssignees, useTicketAnalytics } from "@/query/ticket";
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  categoryLabel,
  type AssigneeOption,
  type TicketPriority,
  type TicketStatus,
} from "@/schema/ticket";


/** The dimension's name as a person would write it.
 *
 *  Derived rather than looked up. The table this replaced named six of the
 *  backend's seven dimensions, so the seventh reached the dropdown as its own
 *  database key, lower case beside six English labels. A table falls behind
 *  the next dimension the same way. Splitting the key apart does not, for
 *  either of the two shapes a key is written in here: camelCase and
 *  snake_case both come out as words.
 *
 *  One shape it still reads wrong is a run of capitals. "SLABreach" comes out
 *  "Slabreach", because the split looks for a lower case letter in front of a
 *  capital and there is none. No dimension is written that way today, and the
 *  answer for one that is would be a short table of exceptions over this, not
 *  a return to naming every dimension by hand.
 */
function dimensionLabel(dimension: string): string {
  const words = dimension
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const CHANNEL_LABELS: Record<string, string> = {
  portal: "Portal",
  email: "Email",
  ai_screening: "Raised by screening",
};

/** The bar label for one bucket of the chosen dimension.
 *
 *  Anything whose stored value is not the word a person would use needs a
 *  branch here. Without one the chart prints the database value, which is how
 *  the assignee breakdown came to label its bars with user ids.
 */
function segmentLabel(
  dimension: string,
  value: string,
  people: AssigneeOption[],
): string {
  if (value === "") return "Not recorded";
  switch (dimension) {
    case "category":
      return categoryLabel(value);
    case "status":
      return TICKET_STATUS_LABELS[value as TicketStatus] ?? value;
    case "channel":
      return CHANNEL_LABELS[value] ?? value;
    case "priority":
      return TICKET_PRIORITY_LABELS[value as TicketPriority] ?? value;
    case "assignee": {
      // A name, not "#11", the same rule the audit log follows. The id is the
      // fallback for a roster that has not loaded and for somebody whose
      // account has since gone. Poor, but better than blank.
      const owner = people.find((person) => String(person.id) === value);
      if (!owner) return `#${value}`;
      // Two agents can carry the same display name, and then the name on its
      // own names neither of them. It also draws two bars captioned alike,
      // which React reads as one row appearing twice. The id comes back as a
      // suffix for those two only.
      const shared = people.some(
        (person) => person.name === owner.name && person.id !== owner.id,
      );
      return shared ? `${owner.name} #${owner.id}` : owner.name;
    }
    // region and userType hold words already: country names, and the role
    // names the platform stores.
    default:
      return value;
  }
}

/** What the server said was wrong with the window, when it was the window.
 *
 *  `serverMessage` in lib/queryError cannot answer this. It reads `msg`,
 *  which is what the rest of the app replies with, while the ticket endpoints
 *  raise DRF validation errors that config/exception_handler reshapes into
 *  `{error, code, fields}`.
 *
 *  Restricted to 400 on purpose: the same envelope carries "Internal server
 *  error" for a 500, and repeating that tells the reader nothing they can act
 *  on, where "from must be earlier than to." is a two-second fix.
 */
function windowProblem(error: unknown): string | undefined {
  if (!isAxiosError(error) || error.response?.status !== 400) return undefined;
  const data = error.response?.data as { error?: unknown } | undefined;
  return typeof data?.error === "string" && data.error.trim() !== ""
    ? data.error
    : undefined;
}

/** Seconds as something a person reads at a glance.
 *
 *  Deliberately coarse: "2h 45m" is the answer to "are we quick?", and a
 *  seconds-precise duration invites reading precision into an average of a
 *  handful of tickets. */
function duration(seconds: number | null) {
  if (seconds === null) return "—";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  if (hours === 0) return `${minutes}m`;
  if (hours < 48) return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
  return `${Math.round(hours / 24)}d`;
}

/** One number, its name, and what it means.
 *
 *  Not a chart: a single quantity has no shape to show, and a one-bar chart is
 *  a number wearing a costume. */
function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-md border p-3">
      {/* Not uppercase with letter spacing any more. At 390px "SATISFACTION"
          ran past the edge of its own card and "HAND-OFFS" broke across two
          lines; the capitals bought nothing that weight and colour were not
          already doing. */}
      <p className="text-muted-foreground text-xs font-medium">{label}</p>
      {/* A duration reads as two numbers when it wraps: "33h" above "58m".
          Kept on one line, and allowed to shrink instead. */}
      <p className="mt-1 text-2xl font-semibold tabular-nums whitespace-nowrap">
        {value}
      </p>
      <p className="text-muted-foreground mt-1 text-xs">{hint}</p>
    </div>
  );
}

/** "26 Aug 2026", never "26/08" or "08/26". */
function namedDay(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-AU", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

function describeWindow(from: string, to: string): string {
  if (from && to) {
    return `Covering ${namedDay(from)} to ${namedDay(to)} inclusive, in UTC.`;
  }
  if (from) return `Covering ${namedDay(from)} onwards, in UTC.`;
  return `Covering everything up to and including ${namedDay(to)}, in UTC.`;
}

export function TicketAnalyticsPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [dimension, setDimension] = useState("region");

  const analytics = useTicketAnalytics({ from, to, dimension });
  const data = analytics.data;
  // The roster the assignee breakdown turns owner ids into names with. Cached
  // under the same key the queue and the audit log already ask for it by, so
  // this costs a request only when neither has been opened.
  const people = useAssignees();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Ticket analytics</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Dates are read as UTC, the same rule the ticket numbering uses. A
          window that starts on 1 March opens at 11am Sydney time.
        </p>
      </div>

      {/* Filters in one row above the charts. */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="from" className="text-xs">
            From
          </Label>
          <Input
            id="from"
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
            className="w-40"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="to" className="text-xs">
            To
          </Label>
          <Input
            id="to"
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            className="w-40"
          />
        </div>
        {/* The native date input renders in the browser's locale, which shows
            "mm/dd/yyyy" on a machine set to US English while the platform's
            users are in Australia — and 03/09 is two different days depending
            on which you assume. The control cannot be told otherwise, so the
            window it produced is echoed back in a form with no ambiguity in
            it: a named month, and the word "inclusive", since the closing
            date now counts the whole day. */}
        <div className="space-y-1">
          <Label className="text-xs">Break down by</Label>
          <Select value={dimension} onValueChange={setDimension}>
            <SelectTrigger className="w-48" aria-label="Break down by">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {/* The list comes from the payload, so a failed request leaves
                  nothing to offer. Falling back to the chosen dimension rather
                  than to "region" keeps the trigger naming what is selected
                  instead of going blank. */}
              {(data?.dimensions ?? [dimension]).map((option) => (
                <SelectItem key={option} value={option}>
                  {dimensionLabel(option)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {(from || to) && (
        <p className="text-muted-foreground -mt-2 text-xs">
          {describeWindow(from, to)}
        </p>
      )}

      {analytics.isError && (
        <p className="text-destructive text-sm" role="alert">
          {wasRefused(analytics.error)
            ? "You do not have access to the ticket dashboard. It is open to the support team and to administrators."
            : (windowProblem(analytics.error) ??
              "Those numbers could not be loaded.")}
        </p>
      )}
      {analytics.isLoading && (
        <p className="text-muted-foreground text-sm">Loading…</p>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Demand · what help is being requested?
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <StatTile
                label="Tickets raised"
                value={String(data.demand.volume)}
                hint="In the selected window"
              />
              <div>
                <p className="mb-1 text-sm font-medium">By category</p>
                <MeasureBars
                  rows={data.demand.categoryMix.map((bucket) => ({
                    label: categoryLabel(bucket.value),
                    value: bucket.count,
                  }))}
                />
              </div>
              <div>
                <p className="mb-1 text-sm font-medium">By channel</p>
                <MeasureBars
                  rows={data.demand.channelMix.map((bucket) => ({
                    label: CHANNEL_LABELS[bucket.value] ?? bucket.value,
                    value: bucket.count,
                  }))}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Flow · where does work slow down?
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <StatTile
                  label="Unassigned"
                  value={String(data.flow.unassignedBacklog)}
                  hint="Nobody has picked it up"
                />
                <StatTile
                  label="Reopens"
                  value={String(data.flow.reopens)}
                  hint="Counted per event"
                />
                <StatTile
                  label="Hand-offs"
                  value={String(data.flow.handOffs)}
                  hint="Passed to someone else"
                />
              </div>
              <div>
                <p className="mb-1 text-sm font-medium">
                  Time since anything happened
                </p>
                <MeasureBars
                  rows={data.flow.ageByStatus.map((row) => ({
                    label:
                      TICKET_STATUS_LABELS[row.status as TicketStatus] ??
                      row.status,
                    value: row.averageSeconds ?? 0,
                  }))}
                  format={duration}
                  emptyMessage="Nothing open in this window."
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Service · how quickly do we respond?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <StatTile
                  label="First reply"
                  value={duration(data.service.firstResponseSeconds)}
                  hint={`Average of ${data.service.answeredCount} answered`}
                />
                <StatTile
                  label="To resolve"
                  value={duration(data.service.resolutionSeconds)}
                  hint={`Average of ${data.service.resolvedCount} resolved`}
                />
                <StatTile
                  label="Overdue"
                  value={String(data.service.overdue)}
                  // Not "no first reply" any more. The client replaced that
                  // rule on 2026-09-04: the clock restarts every time the
                  // requester writes and stops every time support answers, so
                  // a ticket already answered once can still be late. The tile
                  // beside this one is where first replies are measured.
                  //
                  // Word for word what the queue's Overdue card says. The same
                  // number on two screens has to read as the same number.
                  hint="Waiting on support for longer than its priority allows"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Quality · did the support help?
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <StatTile
                  label="Resolved"
                  value={
                    data.quality.resolutionRate === null
                      ? "—"
                      : `${Math.round(data.quality.resolutionRate * 100)}%`
                  }
                  hint={`${data.quality.resolvedCount} of ${data.quality.totalCount}`}
                />
                <StatTile
                  label="Came back"
                  value={String(data.quality.repeatContacts)}
                  hint="People with more than one"
                />
                <StatTile
                  label="Satisfaction"
                  value="—"
                  // Says why rather than showing a zero. A satisfaction score
                  // of nought is a damning number to invent for a survey that
                  // was never sent.
                  hint={
                    data.quality.satisfactionAvailable
                      ? "Average rating"
                      : "Not collected yet"
                  }
                />
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">
                Broken down by {dimensionLabel(dimension).toLowerCase()}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Without the roster every bar below falls back to "#11", which
                  is the very thing this chart was fixed for, so the reason is
                  put on the screen rather than left to be guessed at. Only
                  while the assignee breakdown is the one showing: no other
                  dimension reads the roster, and a warning about labels
                  nobody is looking at is noise. */}
              {dimension === "assignee" && people.isError && (
                <p className="text-destructive mb-2 text-sm" role="alert">
                  The assignee list could not be loaded, so the bars below are
                  labelled with user ids instead of names. Reload to try again.
                </p>
              )}
              <MeasureBars
                rows={(data.segment?.buckets ?? []).map((bucket) => ({
                  label: segmentLabel(dimension, bucket.value, people.data ?? []),
                  value: bucket.count,
                }))}
                unit="tickets"
              />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
