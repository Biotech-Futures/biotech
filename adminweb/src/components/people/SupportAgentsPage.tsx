// Out of the route file for the same reason as TicketQueuePage and
// AdminHomePage: a route file that exports anything but its Route turns
// off autoCodeSplitting for that route, and the components that did it
// cost the main chunk 170 kB between them. Its test imports it from here.
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useGrantSupport,
  useRevokeSupport,
  useSupportRoster,
} from "@/query/ticket";
import { useQueryUsers } from "@/query/user";
import { serverMessage } from "@/lib/queryError";
import { useAuthContext } from "@/provider/AuthProvider";
import { accountStatusNote, type SupportAgent } from "@/schema/ticket";


export function SupportAgentsPage() {
  const { user } = useAuthContext();
  const isAdmin = Boolean(user?.isAdmin);

  const roster = useSupportRoster();
  const grant = useGrantSupport();
  const revoke = useRevokeSupport();

  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<SupportAgent | null>(null);

  // Only searches once there is something to search for: an empty term would
  // pull the whole user list to fill a dropdown nobody opened.
  const candidates = useQueryUsers({ search: search.trim(), limit: 10 });
  // UserAccount.id is a string on this endpoint while the ticket module works
  // in numbers, so every crossing point converts explicitly rather than
  // relying on == somewhere downstream.
  const found = candidates.data?.data.items ?? [];
  const alreadyOn = new Set((roster.data ?? []).map((row) => row.id));

  // The route only checks that you are signed in, so a support agent who is
  // not an admin can reach this URL. The server refuses them either way; this
  // is so they get an answer instead of a table that fails to load.
  if (!isAdmin) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold">Support agents</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Only administrators can change who works the support queue.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Support agents</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Everyone here can open the support queue. Administrators can already
            work it without being listed.
          </p>
        </div>
        {/* Two ways in, one way out. The client asked for a support agent to be
            created "similar to how they can currently create a new admin
            user", and that form lives on the People page — but this is the
            screen somebody comes to when they think "how do I add a support
            person?", so the answer has to be here too.

            A link rather than a second copy of the dialog: the People editor
            already knows which fields each role needs, and a bespoke form here
            would be a second place to keep that in step. The ?role=support
            parameter is the same one the People filter reads.

            The label names where it goes because that is what it does. It
            opens a filtered list, not a form, and the form behind Add User
            there opens on Student, so a button that only said "Create a
            support agent" promised a step it does not take. Filtering to
            support does not make that list the roster either: a role is not
            queue access, and the paragraph below says so. */}
        <Button asChild variant="outline">
          <Link to="/people" search={{ page: 1, role: "support" }}>
            Create a support agent on the People page
          </Link>
        </Button>
      </div>

      <p className="text-muted-foreground -mt-2 max-w-2xl text-sm">
        Adding someone here gives an existing account access to the queue.
        Creating a support agent makes a new account that has queue access and
        nothing else. The button above opens the People page, where the new
        account needs Support picked as its role. Removing access is only
        possible from this page.
      </p>

      {/* Says out loud what an admin would otherwise have to work out by
          comparing two screens. Granting and revoking queue access never
          touch the account's role, on purpose, so the People page goes on
          listing someone as Support after their access is gone, and someone
          whose role reads Mentor can be on this page and working the queue.
          Neither of those is a stale row waiting to catch up.

          The clause about administrators is load-bearing. They reach the
          queue through their admin access and are never listed here, which
          the heading above already says, so an unqualified "only place"
          would send anyone taking stock of queue access straight past every
          one of them. */}
      <p className="text-muted-foreground -mt-4 max-w-2xl text-sm">
        The Role column on the People page records what an account is, not
        whether it can open the queue. Apart from administrators, this page is
        the only place that shows queue access.
      </p>

      <div className="space-y-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name or email to add someone"
          className="w-full sm:w-96"
          aria-label="Search for a person to grant support access"
        />
        {search.trim() !== "" && (
          <ul className="max-w-96 space-y-1 rounded-md border p-2">
            {found.length === 0 && (
              <li className="text-muted-foreground p-1 text-sm">
                {candidates.isLoading ? "Searching…" : "Nobody matched."}
              </li>
            )}
            {found.map((person) => (
              <li
                key={person.id}
                className="flex items-center justify-between gap-2 p-1 text-sm"
              >
                <span>
                  {person.name || person.email}
                  <span className="text-muted-foreground ml-2 text-xs">
                    {person.email}
                  </span>
                  {/* Which of two similar names is the live account. The
                      server refuses a grant to an account that cannot sign in
                      — views_admin._grant_refusal — and answers with a
                      sentence, which is the message below.

                      The mark is not that refusal repeated: this reads
                      is_active, which is false for an invited or a pending
                      account as well, and both of those the server grants.
                      So a row can carry this mark and still go through. The
                      roster table below marks rows off the account's own
                      status, which is the field that decides it, and the two
                      will agree once this endpoint sends the same field. */}
                  {!person.active && (
                    <span className="ml-2 text-xs font-medium text-amber-700">
                      Not an active account
                    </span>
                  )}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={alreadyOn.has(Number(person.id)) || grant.isPending}
                  onClick={() =>
                    grant.mutate(Number(person.id), {
                      onSuccess: () => setSearch(""),
                    })
                  }
                >
                  {alreadyOn.has(Number(person.id)) ? "Already on" : "Grant"}
                </Button>
              </li>
            ))}
          </ul>
        )}
        {/* The other half of the grant guard. The server refuses a student
            account and an account that cannot sign in, and each refusal is a
            sentence written for the admin reading it — "Reactivate it first,
            then grant support access." Nothing here read them, so pressing
            Grant on one of those rows did nothing at all: the row stayed put,
            the button stayed enabled, and the admin pressed it again.

            serverMessage and not ticketRefusalReason: this endpoint answers
            the msg/data envelope directly rather than raising, so the reason
            is in msg and not in the error/code shape the ticket write path
            uses. */}
        {grant.isError && (
          <p className="text-destructive text-sm" role="alert">
            {serverMessage(grant.error) ??
              "That person was not added to the queue."}
          </p>
        )}
      </div>

      {roster.isError ? (
        <p className="text-destructive text-sm" role="alert">
          The roster could not be loaded.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead className="text-right">Open tickets</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {roster.isLoading && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Loading…
                </TableCell>
              </TableRow>
            )}
            {roster.data?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-muted-foreground">
                  Nobody has been granted support access yet. Administrators can
                  still work the queue.
                </TableCell>
              </TableRow>
            )}
            {(roster.data ?? []).map((agent) => (
              <TableRow key={agent.id}>
                <TableCell>
                  {agent.name}
                  {/* Whether this row is somebody working today. Granting and
                      revoking queue access never touch the account, and
                      switching an account off never touches the roster, so a
                      name here can be an account nobody can sign into. The
                      endpoint has sent accountStatus since the grant guard
                      went in; nothing read it, so the row looked exactly like
                      an agent picking up tickets.

                      The mark is the account's own word — Suspended and
                      Deactivated are different decisions and an admin acts on
                      them differently — and it is absent for every status that
                      can still sign in, invited and pending included. Those
                      two are is_active=False as well, so a mark driven off
                      is_active labels a colleague who has not set their
                      password yet as switched off. */}
                  {accountStatusNote(agent.accountStatus) && (
                    <span className="ml-2 text-xs font-medium text-amber-700">
                      {accountStatusNote(agent.accountStatus)} · cannot work the
                      queue
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {agent.email}
                </TableCell>
                <TableCell className="text-right">{agent.openTickets}</TableCell>
                <TableCell>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={revoke.isPending}
                    onClick={() => setPending(agent)}
                  >
                    Revoke
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <AlertDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {pending?.name} from the support queue?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pending && pending.openTickets > 0
                ? `They still own ${pending.openTickets} ticket${
                    pending.openTickets === 1 ? "" : "s"
                  } that nobody else is working on. Revoking does not hand those
                     to anyone else. They stay in this person's name until
                     somebody reassigns them.`
                : "They will lose access to the support queue. Nothing else about their account changes."}{" "}
              {/* The one part of "nothing else changes" worth spelling out.
                  An admin who checks their work on the People page afterwards
                  reads Support next to a name the server now refuses, and the
                  natural next move is to edit that row, which does nothing. */}
              The role listed for them on the People page does not change.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pending) revoke.mutate(pending.id);
                setPending(null);
              }}
            >
              Revoke access
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
