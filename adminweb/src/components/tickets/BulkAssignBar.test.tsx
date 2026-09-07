import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// fireEvent rather than user-event: @testing-library/user-event is not a
// dependency of this app, and adding one is a call for Jinqi rather than a
// detail of a test file.
//
// Opened with the keyboard on purpose. Radix opens a Select on pointerdown,
// but its handler needs a real PointerEvent with pointer capture, and jsdom
// gives it neither — the trigger stays closed and every assertion below would
// pass vacuously. ArrowDown is a documented way in, it works here, and it
// happens to check the control is reachable without a mouse.
const openSelect = (name: RegExp) =>
  fireEvent.keyDown(screen.getByRole("combobox", { name }), { key: "ArrowDown" });

import { BulkAssignBar } from "./BulkAssignBar";
import type { AssigneeOption } from "@/schema/ticket";

// The endpoint returns one list for two consumers. `assignable` marks the
// people the write path will actually accept; everybody else is here so the
// *filter* dropdown can still find their tickets.
const PEOPLE: AssigneeOption[] = [
  { id: 1, name: "Sam Reid", assignable: true },
  { id: 2, name: "Dana Okafor", assignable: true },
  { id: 3, name: "Gone Agent", assignable: false },
];

function open(props: Partial<Parameters<typeof BulkAssignBar>[0]> = {}) {
  return render(
    <BulkAssignBar
      count={3}
      assignees={PEOPLE}
      isPending={false}
      onClear={vi.fn()}
      onAssign={vi.fn()}
      {...props}
    />,
  );
}

describe("BulkAssignBar", () => {
  it("offers only people the write path will accept", () => {
    // The bug this pins: the detail panel filtered on `assignable` and this
    // dropdown did not. Picking the unfiltered name sent a batch the backend
    // refused with a 400, and nothing on screen said so.
    open();

    openSelect(/assign to/i);

    expect(screen.getByRole("option", { name: "Sam Reid" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "Dana Okafor" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Gone Agent" })).toBeNull();
  });

  it("does not let you assign before picking somebody", () => {
    open();
    expect(screen.getByRole("button", { name: /^assign$/i })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("hands the chosen id back as a number", () => {
    const onAssign = vi.fn();
    open({ onAssign });

    openSelect(/assign to/i);
    fireEvent.click(screen.getByRole("option", { name: "Dana Okafor" }));
    fireEvent.click(screen.getByRole("button", { name: /^assign$/i }));

    // Not the string "2": the id goes straight into a JSON body the
    // serializer validates as a primary key.
    expect(onAssign).toHaveBeenCalledWith(2);
  });

  it("says it is working and refuses a second click while it is", () => {
    open({ isPending: true });
    expect(screen.getByRole("button", { name: /assigning/i })).toHaveProperty(
      "disabled",
      true,
    );
  });
});

describe("handing a batch back to the pool", () => {
  it("offers it under the name the filter bar already uses", () => {
    // The endpoint has taken a null assignee since the serializer was written
    // and three backend tests pin it, but no control in the admin app could
    // ask for it. "Unassigned" is what the queue filter calls the same bucket.
    open();

    openSelect(/assign to/i);

    expect(screen.getByRole("option", { name: "Unassigned" })).toBeTruthy();
  });

  it("sends null rather than a person", () => {
    // Not 0 and not the sentinel string: the serializer reads null as "back to
    // the pool" and anything else as a primary key it will refuse.
    const onAssign = vi.fn();
    open({ onAssign });

    openSelect(/assign to/i);
    fireEvent.click(screen.getByRole("option", { name: "Unassigned" }));
    fireEvent.click(screen.getByRole("button", { name: /^unassign$/i }));

    expect(onAssign).toHaveBeenCalledWith(null);
  });

  it("calls the button what it is about to do", () => {
    // A button reading "Assign" that takes the assignee away is the last
    // thing an agent sees before committing a batch of up to two hundred.
    open();

    openSelect(/assign to/i);
    fireEvent.click(screen.getByRole("option", { name: "Unassigned" }));

    expect(screen.queryByRole("button", { name: /^assign$/i })).toBeNull();
    expect(screen.getByRole("button", { name: /^unassign$/i })).toBeTruthy();
  });
});

describe("when the assignee list could not be loaded", () => {
  it("says so instead of opening on a list that looks complete", () => {
    // The endpoint failing leaves `assignees` empty, and the pool line is
    // offered whatever happens — so without this the dropdown opens on one
    // plausible option and reads as a platform with nobody on it.
    open({ assignees: [], assigneesUnavailable: true });

    openSelect(/assign to/i);

    expect(
      screen.getByText(
        "The assignee list could not be loaded, so there is nobody to pick here. Reload to try again.",
      ),
    ).toBeTruthy();
  });

  it("still lets the batch go back to the pool", () => {
    // Nothing about handing tickets back needs the list of people, so the one
    // action that still works has to stay reachable.
    open({ assignees: [], assigneesUnavailable: true });

    openSelect(/assign to/i);

    expect(screen.getByRole("option", { name: "Unassigned" })).toBeTruthy();
  });

  it("says nothing while the list is fine", () => {
    open();

    openSelect(/assign to/i);

    expect(screen.queryByText(/could not be loaded/i)).toBeNull();
  });
});
