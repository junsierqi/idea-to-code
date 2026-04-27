# Verification Matrix

## Purpose

Use this guide when the request spans more than one file, subsystem, or user-visible flow.

## Rule

Do not stop at testing only the edited function or only one happy path. Verify the delivered capability across the implemented flow.

## Coverage Areas

When applicable, cover:

- build or compile
- unit tests
- integration or API flow
- end-to-end user journey
- error or rejection path
- persistence or reload path
- multi-user or multi-session path
- logs or runtime evidence

## Minimum Expectation

For each milestone, try to answer:

- Does the code compile or run?
- Does the main intended flow work?
- Does at least one realistic failure or edge path behave sensibly?
- Can the result be observed in output, state, or UI?

## If Full Coverage Is Not Possible

Say:

- which flows were covered
- which flows were not covered
- why they were not covered
- what residual risk remains

## Strong Close-Out Pattern

For substantial work, verification usually includes a combination of:

- local build
- targeted automated tests
- one or more end-to-end runs
- evidence from output, logs, screenshots, or saved artifacts
