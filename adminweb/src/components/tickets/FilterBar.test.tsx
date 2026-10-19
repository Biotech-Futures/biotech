import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ANY, FilterBar } from "./FilterBar";
import type { AssigneeOption, RegionOption, TicketFilters } from "@/schema/ticket";

const REGIONS: RegionOption[] = [
  { value: "Australia", label: "Australia" },
  { value: "__unknown__", label: "Unknown" },
];

const PEOPLE: AssigneeOption[] = [
  { id: 1, name: "Sam Reid", assignable: true },
  // Kept out of the assign dropdown but deliberately present here: their
  // tickets did not move when the account was switched off, and filtering by
  // them is the only way to find that work in bulk.
  { id: 3, name: "Gone Agent", assignable: false },
];

function show(filters: TicketFilters = {}, onChange = vi.fn()) {
  render(
    <FilterBar
      filters={filters}
      onChange={onChange}
      regions={REGIONS}
      assignees={PEOPLE}
    />,
  );
  return onChange;
}

const openSelect = (name: RegExp) =>
  fireEvent.keyDown(screen.getByRole("combobox", { name }), { key: "ArrowDown" });

describe("FilterBar search box", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not raise a filter change on every keystroke", () => {
    // The queue query is a COUNT plus a page of rows. Typing an eight-letter
    // ticket number used to issue eight of them.
    const onChange = show();
    const box = screen.getByRole("textbox", { name: /search tickets/i });

    for (const value of ["S", "SU", "SUP", "SUP-"]) {
      fireEvent.change(box, { target: { value } });
    }

    expect(onChange).not.toHaveBeenCalled();
  });

  it("raises exactly one change once the typing settles", () => {
    const onChange = show();
    const box = screen.getByRole("textbox", { name: /search tickets/i });

    for (const value of ["S", "SU", "SUP", "SUP-"]) {
      fireEvent.change(box, { target: { value } });
    }
    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ search: "SUP-" });
  });

  it("shows what was typed straight away", () => {
    // The debounce is on what leaves the component, not on the box itself. A
    // laggy-feeling input is how a delay like this gets reported as a bug.
    show();
    const box = screen.getByRole("textbox", { name: /search tickets/i });

    fireEvent.change(box, { target: { value: "mia" } });

    expect((box as HTMLInputElement).value).toBe("mia");
  });

  it("empties the box when the parent clears the filters", () => {
    // Clear filters sets search to "" from the outside; nothing else would
    // reset the local draft, and a stale word left in the box reads as a
    // filter that is still applied.
    const { rerender } = render(
      <FilterBar
        filters={{ search: "mia" }}
        onChange={vi.fn()}
        regions={REGIONS}
        assignees={PEOPLE}
      />,
    );
    expect(
      (screen.getByRole("textbox", { name: /search tickets/i }) as HTMLInputElement).value,
    ).toBe("mia");

    rerender(
      <FilterBar
        filters={{}}
        onChange={vi.fn()}
        regions={REGIONS}
        assignees={PEOPLE}
      />,
    );

    expect(
      (screen.getByRole("textbox", { name: /search tickets/i }) as HTMLInputElement).value,
    ).toBe("");
  });
});

describe("FilterBar dropdowns", () => {
  it("keeps agents who can no longer be assigned in the assignee filter", () => {
    // The mirror image of BulkAssignBar: this list must NOT filter on
    // `assignable`. Dropping them here would make every ticket still in their
    // name invisible in bulk — not unassigned, so no counter shows it, and no
    // value to filter by.
    show();

    openSelect(/filter by assignee/i);

    expect(screen.getByRole("option", { name: "Gone Agent" })).toBeTruthy();
  });

  it("carries the Unknown region bucket as a sentinel, not an empty value", () => {
    // An empty query parameter reads as "no filter" everywhere else on the
    // platform, so the bucket needs a value of its own.
    const onChange = show();

    openSelect(/filter by region/i);
    fireEvent.click(screen.getByRole("option", { name: "Unknown" }));

    expect(onChange).toHaveBeenCalledWith({ region: "__unknown__" });
  });

  it("turns the Any option back into no filter at all", () => {
    const onChange = show({ status: "open" });

    openSelect(/filter by status/i);
    fireEvent.click(screen.getByRole("option", { name: /any status/i }));

    expect(onChange).toHaveBeenCalledWith({ status: "" });
    expect(ANY).toBe("__any__");
  });
});
