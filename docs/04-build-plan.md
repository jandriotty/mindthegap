# Implementation scope and acceptance criteria

## Phase 1 — Agree on the flow

Confirm the outreach-list/map proportions and whether implementation should begin immediately. Store documentation and reference images in this folder.

## Phase 2 — Working demo

- Home, call-sheet workspace, client panel, follow-up, and guide.
- Explicitly synthetic fixtures and a simulated advisory.
- Claim, adaptive questions, outcome logging, task assignment, retry, and support verification.
- Document the storage behavior according to the implementation: browser-local storage or server storage.
- Restore the original data with Reset demo.
- Calculate group counts from the data; do not use arbitrary numbers in individual screens.

## Phase 3 — Real-data integration

After confirming the official schema and supplied scope, build an adapter. For NWS, HVI, and related sources, read each repository skill’s Search trigger and verify its access method and limitations. Do not claim that live queries or real-data integration are complete until they have been implemented and tested.

## Deferred from the MVP

- Arbitrary weighted clinical-risk scores and unsupported confidence percentages.
- Real SMS, email, or phone calls.
- Patient data, real authentication, or EHR integration.
- An unvalidated clinical decision table.
- Guarantees of real-time resource capacity.

## Primary acceptance criteria

1. Every relevant screen identifies a simulated event as simulated.
2. The list and counts match across all three groups.
3. Recently verified answers are omitted from repeated questions but remain editable.
4. An Unreachable client remains on the list and receives a retry or escalation.
5. An Accepted task alone does not move a plan to Plan confirmed.
6. A client moves to the completed group only after all required support is verified.
7. Recording a new need returns a previously completed plan to review.
8. Consent Unknown or No displays a review state instead of proceeding with standard outreach.
9. Neighborhood map context remains separate from individual facts.
10. Refresh, reset, keyboard navigation, and narrow-screen behavior are tested.

## Communicating deliverable status

After implementation, update the README with actual run instructions, verification results, the mock/live distinction, and remaining limitations. A proposal in the documentation does not mean that a feature has been implemented.
