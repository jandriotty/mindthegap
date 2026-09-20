# Page structure and design direction

## Visual direction

Use generous spacing, thin borders, white and light neutral backgrounds, dark primary buttons, and restrained status accents. The current interface applies an Inter-based, neutral-first system inspired by modern utility CSS: slate surfaces, one sky-blue information accent, and semantic colors used only for status indicators.
Do not reproduce the dark video overlays or playback controls from the early visual references.
All interface and planning-document copy is in English.

## 1. Home

- Header: Heat Check-In / Overview / Call sheet / Data & provenance.
- Eyebrow: Behavioral health · Extreme heat.
- Headline: Turn a heat alert into a human check-in.
- Description: One explained call list, only the questions that matter, and an owner for every next step.
- CTA: Open team call sheet.
- Three workflow explanations: Prioritize / Check in / Follow through.
- Operational users can enter the workspace directly.

## 2. Call-sheet workspace

- Top: team name, event state, and Simulate advisory.
- Event banner: event dates, affected area, source timestamp, and simulated/live distinction.
- Three group filters with calculated counts.
- Left side: team service-area and neighborhood context map.
- Right side: client outreach list. Selecting a client changes this area into the call card.
- Primary actions: Open card, Claim, and Print call sheet.
- Printed output includes only the necessary information, owner, print date, and synthetic-data label.

The split layout keeps the map and outreach workflow side by side on wide screens. The map is not a visualization of individual risk. It does not display real client addresses, and all demo locations are explicitly labeled as synthetic or neighborhood context.

## 3. Client call card — right detail panel

- Synthetic client ID, priority group, and owner.
- Why flagged / Known / Unknown or stale.
- Consent and preferred contact method.
- Adaptive questions and note.
- Outcome: Reached / Unreachable / Declined.
- Save check-in → reviewable action draft.
- Close or Back to list.

## 4. Follow-up view — workspace tab

- Need, client, assigned role, due date, and status.
- Filters: Open / Blocked / Verified.
- When support is verified, store the recorder, timestamp, and verification evidence.
- Supervisors can identify unassigned, overdue, and unsuccessful-contact cases.

## 5. Guide — supporting panel

- Open and close from the workspace.
- Suggested questions: Why is this client listed? / What is still unknown? / What happens after an unsuccessful call?
- Label it as a scripted demo guide until a real AI connection exists.
- Limit its scope to current client facts and workflow explanations.
- Prioritize one panel at a time so the Guide does not cover the call card’s primary actions.

## Shared states

- No advisory: keep the readiness list available.
- No matching clients: state that no clients in the caseload match the active event.
- All confirmed: show the next review point while keeping the full list accessible.
- Data unavailable: show that information is unavailable; do not interpret missing information as safety.
- Save failure: preserve the input and support retry.
- Mobile: prioritize the list, place the map below it, and use a full-width detail view.
- Accessibility: pair color with text, support keyboard navigation, restore focus after closing panels, and provide labels for inputs.
