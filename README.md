# idea-to-code

A Codex skill for turning rough product ideas into implemented, verified, and acceptance-tracked software changes.

It helps agents structure long-running delivery work through requirements, milestones, verification gates, blockers, traceability, and final reports. The skill is useful when a request starts as a product idea or broad feature direction and should end as working code rather than a design note.

## Repository Structure

This repository is the development wrapper for the `idea-to-code` Codex skill. The installable skill source is only:

```text
skills/idea-to-code/
```

Repository-root files such as this `README.md` and `scripts/install_skill.py` are maintenance scaffolding for developing and installing the skill. They are not installed as skill runtime instructions.

Runtime behavior and agent-facing workflow rules must live under `skills/idea-to-code/`, primarily in `SKILL.md`, the bundled script, and focused reference files. Do not add repository-root rule files such as `AGENTS.md` to define skill behavior; they will not be installed by `scripts/install_skill.py`.

## Use When

- A task starts as a rough product idea or feature concept.
- Work spans multiple milestones, subsystems, or user-facing flows.
- The user expects implementation, testing, iteration, and acceptance tracking.
- Progress needs to survive context resets through saved delivery artifacts.

## What's Included

- `skills/idea-to-code/SKILL.md` - agent workflow instructions
- `skills/idea-to-code/scripts/idea_to_code_bundle.py` - delivery artifact manager
- `skills/idea-to-code/references/` - focused workflow references
- `skills/idea-to-code/agents/openai.yaml` - Codex/OpenAI UI metadata
- `README.md` and `scripts/install_skill.py` - repository maintenance files, not installed runtime instructions

## Requirements

- Python 3.8+
- No runtime Python package dependencies

## Install

Run the installer from the repository root:

```bash
python scripts/install_skill.py
```

This installs or updates the skill at:

```bash
$HOME/.codex/skills/idea-to-code
```

To preview the update without writing files:

```bash
python scripts/install_skill.py --dry-run
```

The bundled script can also be used directly from this repository:

```bash
python skills/idea-to-code/scripts/idea_to_code_bundle.py --help
```

## Maintain

For clear, low-risk, single-file changes, use `quickstart` to generate the ready bundle and print the READY TASK output:

```bash
python skills/idea-to-code/scripts/idea_to_code_bundle.py quickstart \
  --root "$(pwd)" \
  --slug readme-note \
  --title "Add README note" \
  --idea "Add one concise README sentence." \
  --file README.md \
  --task "Add one concise README sentence." \
  --unique
```

Paste the generated READY TASK output before editing files.
For low-risk changes, that output is a transparency step rather than a separate approval gate.
This READY TASK visibility requirement also applies to README-only maintenance edits.
Use `--json` only for automation that needs machine-readable quickstart output without READY text. Use `implementation show-ready` to reprint or refresh the READY TASK output for an already-ready bundle.

Run the regression suite before publishing:

```bash
python skills/idea-to-code/scripts/test_idea_to_code_bundle.py
```

Inspect role evidence requirements before recording a role gate:

```bash
python skills/idea-to-code/scripts/idea_to_code_bundle.py role explain --role validator
```
