# Evidence Capture

## Purpose

Use this guide when the delivered result has visible UI, rendered output, or runtime behavior that should be demonstrated with evidence.

## Evidence Priority

Prefer evidence in this order when available:

1. screenshot of the actual result
2. test output tied to the same state
3. runtime log or command output
4. code diff or file reference

Do not claim visual completion without visual evidence when screenshot capture is available.

## When To Capture Screenshots

Capture screenshots when:

- the task changes UI or layout
- the task affects visual rendering
- the task introduces visible states
- the user needs acceptance review on look and feel

Typical states to capture:

- main happy path
- empty state
- loading state
- error or rejection state
- success state
- responsive or alternate viewport state when relevant

## Screenshot Rules

- Use real output from the current run, not stale files from an earlier iteration.
- Name screenshots so they match the flow or test they prove.
- Mention what each screenshot demonstrates.
- Prefer screenshots that align with tested states, not random snapshots.
- If the screenshot comes from an automated test, say that.

## Non-Visual Evidence

For backend, CLI, protocol, or infrastructure work, collect:

- build output
- test summaries
- API or socket responses
- logs that prove the flow executed
- saved artifacts produced by the run

## If Screenshots Are Not Available

Say explicitly:

- that screenshot capture was not available
- why it was unavailable
- what alternative evidence is provided instead

## Report Integration

In the final report, tie each screenshot or artifact to:

- the flow or state it proves
- the verification step that produced it
- any limitation in what it demonstrates
