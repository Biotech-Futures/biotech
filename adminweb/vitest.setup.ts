import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount between tests. Without it every render stacks up in the same
// document and getByText starts finding the previous test's markup, which
// fails in whichever order the file happens to run in.
afterEach(() => {
  cleanup();
});

// Radix primitives (Select, Dialog, the drawer) measure and observe elements
// that jsdom does not implement. These are the three that come up; each throws
// "not a constructor" or "is not a function" at render time without a stub.
class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

globalThis.ResizeObserver ??= NoopObserver as never;
globalThis.IntersectionObserver ??= NoopObserver as never;
globalThis.DOMRect ??= class {
  constructor(
    public x = 0,
    public y = 0,
    public width = 0,
    public height = 0,
  ) {}
  get top() {
    return this.y;
  }
  get left() {
    return this.x;
  }
  get right() {
    return this.x + this.width;
  }
  get bottom() {
    return this.y + this.height;
  }
  static fromRect() {
    return new DOMRect();
  }
  toJSON() {
    return {};
  }
} as never;

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
