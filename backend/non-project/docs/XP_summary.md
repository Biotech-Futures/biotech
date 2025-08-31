# Extreme Programming (XP)

Extreme Programming (XP) is a lightweight methodology used to rapidly develop high-quality software that provides the highest value for the customer.

---

## 12 Core Practices of XP

### 1. The Planning Game

- **Business team** writes up user stories (desired features for the system).
- **Development team** estimates the effort for each story and determines how much can be produced in a time interval (iteration or sprint).
- **Business** decides the order in which the stories will be implemented.

### 2. Small Releases

- Start with the smallest useful feature set.
- Release early and often, adding a few features each time.

### 3. System Metaphor

- Each project has an organizing metaphor, which provides an easy-to-remember naming convention.

### 4. Simple Design

- Use the simplest possible design that gets the job done.

### 5. Continuous Testing

- Write a failing test before coding any feature.
- The feature implementation is complete once the test passes.

**Types of Tests:**

- **Unit Tests**: Automated tests written by developers to verify functionality as it is implemented.
- **Acceptance Tests (Functional Tests)**: Specified by the client to ensure the overall system works as intended.

### 6. Refactoring

- Remove duplicate or unnecessary code created during development.

### 7. Pair Programming

- All production code is written by **two programmers** at one machine.
- All code is reviewed as it is written.

### 8. Collective Code Ownership

- Any developer is expected to work on **any part** of the codebase at any time.

### 9. Continuous Integration

- All changes are integrated into the codebase **at least daily**.
- Tests must pass **100%** both before and after integration.

### 10. 40-Hour Work Week

- Overtime is discouraged.
- In crunch mode, only **one week** of overtime is allowed.

### 11. On-site Customer

- The development team has continuous access to a **real, live client**.

### 12. Coding Standards

- Everyone codes to the **same standards**.

---

## Supporting Principles and Acronyms

### YAGNI — _You Aren’t Gonna Need It_

Only implement what is needed for current requirements; avoid speculative features.

### DTSTTCPW — _Do The Simplest Thing That Could Possibly Work_

Favor simplicity and clarity over complexity.

### OAOO — _Once and Only Once_

Eliminate duplication in code and tests.

---

## What an XP Project Looks Like

- **Team setup**: Programmers often share a common work area for better communication.
- **Iteration length**: Typically 1–3 weeks; same length for each iteration.
- **Iteration cycle**:
  1. Planning meeting with the customer.
  2. Developers sign up for tasks they can complete within the iteration.
  3. All production code is written **test-first** and in pairs.
  4. Deliver a working, bug-free system at iteration end.
  5. Release to end users is straightforward because the system is always in a shippable state.

---

## Project Size Suitability

- Works best for **up to ~12 programmers** (can stretch to ~24 with difficulty).
- For larger projects, consider splitting into multiple XP teams.

---

## Comparisons with Other Processes

- **Scrum** – Very similar philosophy, with more focus on removing impediments and daily stand-ups.
- **Feature Driven Development (FDD)** – More hierarchical; chief programmer directs class owners and teams.
- **RUP** – XP can be seen as a minimal instance of the Rational Unified Process.
- **CMM** – Shares the discipline spirit, but XP minimizes paperwork and meetings.

---

## Common Objections & Responses

- **"XP is cowboy coding"** – In reality, XP enforces more discipline: no code without a failing test, pair programming, continuous integration, and regular releases.
- **"Pair programming cuts productivity in half"** – Studies show pairs are _more_ productive overall, producing higher quality code with fewer defects.
- **"Simple design won’t scale"** – XP relies on continual refactoring to maintain scalability.
- **"YAGNI leads to dead-ends"** – Rare, and outweighed by the time saved avoiding premature complexity.

---

## Role descriptions

**Tracker**
As the name suggests the tracker logs and keeps track of team member progress. If project direction falls off course the tracker is also responsible for bringing it back on track through meetings and coaching.

**Manager**

- Oversees and determines the planning game
- Monitoring the planning game, fix deviations and modifying the rules
- Scheduling and conducting release planning and other meeting
-

---

## Reference

- https://jera.com/techinfo/xpfaq
