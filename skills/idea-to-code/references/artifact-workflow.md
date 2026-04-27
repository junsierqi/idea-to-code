# Artifact Workflow

## Purpose

Keep delivery progress visible through saved artifacts, not just chat messages, and make progress machine-readable (`status.json`) so a later session can pick up where an earlier one stopped.

## Bundle Directory

For substantial tasks, create:

`<project-root>/.idea-to-code/<slug>/`

Files:

- `00-idea.md` — the original idea and desired outcome
- `01-requirements.md` — concrete requirements (target / user / flow / success / non-goals)
- `02-prd.md` — lightweight PRD
- `03-milestones.md` — current phase + milestone history
- `04-verification.md` — coverage expectations + verification history
- `05-final-report.md` — auto-rolled-up at `finalize`
- `06-acceptance.md` — acceptance snapshot at `finalize`
- `status.json` — machine-readable state

## Script Location

The script is installed with this skill:

```
<path-to-idea-to-code>/scripts/manage_delivery_bundle.py
```

Invoke with Python 3.8+ from any working directory. Examples below assume bash (works on Windows, macOS, Linux).

Resolve `<path-to-idea-to-code>` to the installed skill directory. When this repository root is the current working directory, `python skills/idea-to-code/scripts/manage_delivery_bundle.py ...` is correct. When the skill directory itself is the current working directory, `python scripts/manage_delivery_bundle.py ...` is correct. When installed under Codex, the path is commonly `$HOME/.codex/skills/idea-to-code/scripts/manage_delivery_bundle.py`.

For brevity, the examples below use `$BUNDLE` / `$ROOT` / `$SLUG`. In actual tool calls, inline the resolved Python command and `$(pwd)` / `<slug>` directly when that is clearer.

```bash
# Conceptual shorthand used in docs only:
BUNDLE="python \"<path-to-idea-to-code>/scripts/manage_delivery_bundle.py\""
ROOT="$(pwd)"
SLUG="my-feature"

# Example actual call when this repository root is the current working directory:
python skills/idea-to-code/scripts/manage_delivery_bundle.py status --root "$(pwd)" --slug my-feature
```

## Subcommands

### Initialize

```bash
$BUNDLE init --root "$ROOT" --slug "$SLUG" --title "<task title>"
# Optional:
#   --unique              prefix slug with YYYYMMDD-HHMM to avoid collisions
#   --idea "<seed text>"  seed 00-idea.md's User Idea section
```

Idempotent — existing files are not overwritten.

### Update requirements / PRD / idea

```bash
$BUNDLE update --root "$ROOT" --slug "$SLUG" --file requirements --content-file ./reqs.md
$BUNDLE update --root "$ROOT" --slug "$SLUG" --file prd           --content  "## Goal ..."
$BUNDLE update --root "$ROOT" --slug "$SLUG" --file idea          --content  "..."  --append
$BUNDLE update --root "$ROOT" --slug "$SLUG" --file verification  --content-file ./coverage.md
```

`--file` accepts `idea | requirements | prd | verification`. Pass `--content` inline or `--content-file <path>`. Default replaces the file; `--append` appends.

`03-milestones.md`, `05-final-report.md`, `06-acceptance.md` are script-managed (checkpoint / finalize overwrite them) and therefore not accepted by `update` — use `rebuild-markdown` to regenerate 03/04 from `status.json`, and `finalize` (or its `--force`) for 05/06.

### Register requirements (trace matrix)

```bash
$BUNDLE requirement add --root "$ROOT" --slug "$SLUG" \
  --id REQ-1 --description "User can create a note" --type functional

$BUNDLE requirement list   --root "$ROOT" --slug "$SLUG"
$BUNDLE requirement close  --root "$ROOT" --slug "$SLUG" --id REQ-4 --note "dropped by user"
$BUNDLE requirement remove --root "$ROOT" --slug "$SLUG" --id REQ-4   # use close if it was ever open
```

`--type` is `functional | nonfunctional | constraint`. IDs must be unique within a bundle. See `trace-matrix.md` for full semantics.

### Retroactively link a past milestone to requirements

```bash
$BUNDLE link --root "$ROOT" --slug "$SLUG" \
  --milestone "<exact past milestone name>" \
  --covers   "REQ-1,REQ-3" [--replace]
```

Use when resuming an older bundle whose milestones predate `--covers`, or when a requirement was added late. Default merges; `--replace` overwrites. Unknown REQ-IDs are rejected.

### Record a milestone

```bash
$BUNDLE checkpoint --root "$ROOT" --slug "$SLUG" \
  --milestone "<name>" \
  --delivered "<what changed>" \
  --verified  "<how it was verified>" \
  --next      "<next step>" \
  --focus     "<current focus>" \
  --gate      "<next gate>" \
  --gate-status pass \    # pass | partial | fail
  --covers    "REQ-1,REQ-3"
```

Writes to `03-milestones.md`, `04-verification.md`, and `status.json`. Rewrites `## Current Phase`. Unknown REQ-IDs in `--covers` cause the command to fail early.

### Record a blocker

```bash
$BUNDLE block --root "$ROOT" --slug "$SLUG" \
  --reason "<concrete cause>" \
  --need   "<decision or dependency needed>"
```

Sets `status.state = blocked`. Also appends an entry to `03-milestones.md` and flips `## Current Phase` to blocked.

### Clear a blocker

```bash
$BUNDLE unblock --root "$ROOT" --slug "$SLUG" --note "<resolution>"
```

### Inspect status

```bash
$BUNDLE status --root "$ROOT" --slug "$SLUG"          # summary
$BUNDLE status --root "$ROOT" --slug "$SLUG" --full   # + milestones + blocks
```

Output is JSON. Reads well in chat and can be piped into `jq`.

### Finalize

```bash
$BUNDLE finalize --root "$ROOT" --slug "$SLUG" \
  --summary       "<implementation summary>" \
  --verification  "<verification summary>" \
  --risks         "<remaining risks>" \
  --acceptance    "<scope delivered>" \
  --gate-status   pass \
  --decision      accepted \
  --acceptance-notes "<optional>" \
  --deferred         "<optional>"
```

- `--gate-status`: `pass | partial | fail`
- `--decision`: `accepted | accepted-with-followup | not-accepted`
- Rolls up recorded milestones into `05-final-report.md`.
- If `05-final-report.md` or `06-acceptance.md` were manually edited, they are backed up to `*.bak` before being overwritten. Pass `--force` to skip the backup.
- `state` becomes `completed` only when `--decision accepted`; otherwise it becomes `closed` so the bundle reflects reality.
- **Integrity cross-check**: finalize refuses when the claim contradicts the bundle — `--gate-status pass` with any failing / uncovered / partial REQ aggregate, or `--decision accepted` with any failing / uncovered REQ or unresolved blocker. The error lists exactly which REQ / blocker caused the refusal. Pass `--force` to override; the overrides (and which checks were bypassed) are recorded in a `## Force Overrides` section of `05-final-report.md` and in `status.force_overrides`.

### Verify bundle completeness

```bash
$BUNDLE verify --root "$ROOT" --slug "$SLUG"
```

Prints a JSON report and exits non-zero when:

- required files are missing
- `status.json` has no milestones
- `00-idea.md` is still on the template
- an open requirement has no covering milestone (**trace matrix gap**)
- a requirement's aggregate gate is `fail`

Use it as the last check before claiming done.

### Regenerate 03-milestones.md from status.json

```bash
python ".../manage_delivery_bundle.py" rebuild-markdown \
  --root "$ROOT" --slug "$SLUG"
```

Use when historical formatting drifted (missing blank lines between entries, manually edited sections, schema upgrade to new `covers` field). `status.json` stays authoritative; the old `03-milestones.md` is backed up to `.bak` before rewrite.

### Bilingual / translated report

```bash
$BUNDLE translate-report --root "$ROOT" --slug "$SLUG" \
  --source 05-final-report.md --lang en
# or --lang zh, --lang ja. Optional: --target 05-final-report.english.md
```

Creates a sibling file with section headings translated. Body prose is left verbatim and must be translated with Edit.

## Rule

For substantial work, do not rely only on the chat transcript. Keep the bundle updated as the project evolves.

- `init` creates the working artifact set.
- `update` fills the idea / requirements / PRD docs instead of leaving them as empty templates.
- `checkpoint` records milestone history plus current focus, next gate, and gate status.
- `block` / `unblock` make external blockers first-class state, not a free-form chat comment.
- `status` makes progress machine-readable and easy to inspect.
- `finalize` closes the bundle with a rolled-up final report and acceptance snapshot.
- `verify` catches bundles that look done but are missing required content.
