# idea-to-code

A Codex skill for turning rough product ideas into implemented, verified, and acceptance-tracked software changes.

It helps agents structure long-running delivery work through requirements, milestones, verification gates, blockers, traceability, and final reports. The skill is useful when a request starts as a product idea or broad feature direction and should end as working code rather than a design note.

## Use When

- A task starts as a rough product idea or feature concept.
- Work spans multiple milestones, subsystems, or user-facing flows.
- The user expects implementation, testing, iteration, and acceptance tracking.
- Progress needs to survive context resets through saved delivery artifacts.

## What's Included

- `skills/idea-to-code/SKILL.md` - agent workflow instructions
- `skills/idea-to-code/scripts/manage_delivery_bundle.py` - delivery artifact manager
- `skills/idea-to-code/references/` - focused workflow references
- `skills/idea-to-code/agents/openai.yaml` - Codex/OpenAI UI metadata

## Requirements

- Python 3.8+
- No runtime Python package dependencies

## Install

Copy or symlink `skills/idea-to-code/` into your Codex skills directory, commonly:

```bash
$HOME/.codex/skills/idea-to-code
```

The bundled script can also be used directly from this repository:

```bash
python skills/idea-to-code/scripts/manage_delivery_bundle.py --help
```
