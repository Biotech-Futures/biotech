/**
 * What "Force delete" destroys, written once.
 *
 * There were seven copies of this sentence — three checkbox labels, two code
 * comments and two backend docstrings — and they had drifted: every one of
 * them listed chat messages, uploaded resources, workshops and match runs, and
 * none of them mentioned support tickets, which the purge has destroyed since
 * the ticketing work landed. An admin clearing out a student who has left was
 * told four things would go and five did, the fifth being enquiries an agent
 * may still be working.
 *
 * Adding tickets to all seven would only have moved the drift a release later,
 * so the copies are gone instead: this component is the only place the list
 * exists, and the two remaining backend docstrings point at the code that does
 * the deleting rather than restating it.
 *
 * Deliberately just the sentence — no checkbox, no state. Each page keeps its
 * own control and its own wiring; what they share is the promise made to the
 * person clicking it.
 */
export function ForceDeleteNotice({
  subject,
}: {
  subject: "user" | "supervisor" | "student";
}) {
  return (
    <span>
      Force delete — also permanently delete each {subject}'s chat messages,
      uploaded resources, workshops, match runs, and any support ticket they
      raised, including the replies and internal notes support staff wrote on
      it. Required to remove accounts that have any activity.
    </span>
  );
}
