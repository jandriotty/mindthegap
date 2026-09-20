# User flow — Working draft

## Confirmed decisions

1. Workspace layout: split the map and outreach list evenly.
2. Process: agree on the user flow together before implementation.

## Next decision

Proposed behavior: when a client is selected, keep the map on the left and replace the list on the right with the call card. The map provides context for the team’s service area and cooling resources; individual address pins are excluded by default. **Back to list** restores the previous list, filters, and scroll position.

## Recommended primary flow

Introduction page → Open call sheet → Team heat outreach list → Select client → Claim → Verify contact permission → Ask call questions → Record outcome → Assign follow-up → Verify support → Reuse updated information during the next heat event.

### 1. Entry

- Presentation entry: **Open call sheet** on the landing page.
- Operational entry: open the relevant team and event list directly from a delivered link.
- The initial demo uses a fixed synthetic team. Do not imply that real authentication or message delivery is implemented.

### 2. Heat event

- Start the demo with **Simulate advisory**.
- The banner displays the area, start/end time, information update time, and a Simulated label.
- If a real API is added, continue to distinguish demo events from live events.
- The default caseload and readiness status remain available when no event is active.

### 3. Outreach list

- Default tabs: Unresolved needs / Needs verification / Plan confirmed.
- Each row: synthetic ID, primary reason, last verification, contact status, and owner.
- Top-K represents today’s working volume; it does not hide or exclude the remaining clients.
- Hard-to-reach clients are not automatically deprioritized; display retry or escalation instead.
- Group counts are calculated from the actual demo data.

### 4. Client card and claim

- When a client is opened, separate Known, Needs verification, and Why this client appears.
- Claiming a client displays In progress and the assigned owner.
- If another team member already owns the client, show the owner and status instead of initiating duplicate outreach.
- If contact consent is No or Unknown, place the client in a review state for approved organizational procedures. The demo does not place real calls.

### 5. Adaptive call card

Question pool:

1. Do you currently have access to working cooling?
2. Is cost or equipment failure making it difficult to use?
3. Do you have another cool place where you can stay?
4. Would you need transportation support to get there?
5. Do you have a question for your clinician?
6. Can we confirm your preferred contact method and contact information?

- Summarize recently verified fields without asking them again.
- Reconfirm fields that are old or affected by a changed circumstance.
- Existing answers remain editable.
- Record and route clinical questions; do not provide automated medical advice.

### 6. Outcome branches

**Reached, no open need:** Move to Plan confirmed when all required information is current and all existing needs are resolved.

**Reached, support needed:** Draft one task per need → user review → assign an owner and due date → Open.

**Unreachable:** Record the reason and time → schedule a retry or supervisor escalation. Do not mark the plan complete.

**Declined:** Record the refusal and preference, then place the case in manual review. Do not treat it as completed support.

**Consent unclear:** Move to contact-permission review.

### 7. Verify real support

Task: Open → Accepted → In progress → Support verified.
Exceptions: Blocked / Cancelled with reason. Cancellation does not count as resolution.

- Distinguish a transportation booking or repair request from the actual resolution of the need.
- If a resource is unavailable, retain Blocked status, alternatives, and supervisor review.
- Move to Plan confirmed only when all required needs are resolved and the plan remains current.

### 8. Next event

- Preserve previous answers, sources, and verification dates.
- Current, valid answers reduce repeated questions.
- Return a client to the verification list when circumstances change, a new need appears, or information expires.
- Duplicate-alert suppression must not suppress a new need.

## Demo scenario

Simulate advisory → review the three groups → open a client with unknown cooling status → Claim → record broken cooling and transportation need → assign two tasks → record another client as Unreachable → create a retry → verify support and move the first client to Plan confirmed → display the saved answers during the next event.
