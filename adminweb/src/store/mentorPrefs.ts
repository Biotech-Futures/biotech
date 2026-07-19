import { create } from "zustand";
import { persist } from "zustand/middleware";

type MentorPrefsState = {
  /** Show mentors with no remaining capacity in the pick surfaces. */
  showFullMentors: boolean;
  setShowFullMentors: (value: boolean) => void;
};

// Persisted so the choice is one setting shared by every mentor pick surface,
// not three independent bits of component state.
export const useMentorPrefs = create<MentorPrefsState>()(
  persist(
    (set) => ({
      showFullMentors: false,
      setShowFullMentors: (value) => set({ showFullMentors: value }),
    }),
    { name: "adminweb.mentorPrefs" },
  ),
);

/**
 * Whether a mentor should be offered in a pick list.
 *
 * `currentMentorId` keeps the group's own assigned mentor visible even when full
 * — otherwise a replace `<select>` loses its own value and renders blank.
 */
export function isMentorSelectable(
  mentor: { mentorId: number; remainingCapacity: number },
  showFull: boolean,
  currentMentorId?: number | null,
): boolean {
  return (
    showFull ||
    mentor.remainingCapacity > 0 ||
    (currentMentorId != null && mentor.mentorId === currentMentorId)
  );
}
