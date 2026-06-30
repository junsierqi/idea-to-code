# Verification And Evidence

## Purpose

Use this reference when validating behavior, recording evidence, collecting screenshots or runtime artifacts, reviewing acceptance, or closing a task.

## Acceptance Philosophy

Validation is evidence that the skill stayed intelligent, controllable, and evidence-backed, not merely that a command exited zero. For idea-to-code itself, accepted changes must show that the user's idea was understood, improved where useful, executed through visible TASK/REQ scope, and closed without orphaned branches, contradictory numbering, or unverified independent-agent claims. The durable evidence must be recoverable from the installed skill guidance and bundle state.

## Validation Types

Every validation claim must name one:

- `real-product-path`: same user-observable or product entry point affected by the task.
- `mock-only`: mocked service or dependency.
- `fixture-only`: fixture or sample data path.
- `source-only`: code, docs, type, or static inspection.
- `dom-only`: DOM/render structure without full product behavior.
- `manual-inspection`: human inspection path with concrete file, screen, or artifact.
- `unverified`: not validated; must name the missing dependency or deferral.

Use `real-product-path` for real product behavior when locally available. Lower-level evidence can support it but should not be claimed as equivalent.

Every TASK/IMP `Planned Verification` section must name one approved validation type before READY. This makes validation strength explicit during planning and prevents missing-type failures from being discovered only at checkpoint or finalize.

## Verification Summary

Before checkpointing or finalizing, summarize:

```text
=== VERIFICATION SUMMARY: <milestone> ===
Implementation Items:
- IMP-1 PASS|PARTIAL|FAIL - <evidence or missing piece>
- IMP-2 PASS|PARTIAL|FAIL - <evidence or missing piece>
[ ] Code change lands in: <file(s)>
[ ] Build/compile: <command + result>
[ ] Tests/runtime check: <command + result>
[ ] Behavior observed: <log / output / screenshot reference>
Result: PASS | PARTIAL | FAIL
===
```

Rollup:

- `PASS`: all critical items pass with evidence.
- `PARTIAL`: non-critical or explicitly deferred gaps remain.
- `FAIL`: critical item failed, is missing, or lacks required validation.

## Fact / Hypothesis / Decision / Verification

Use these categories when diagnosing failures, explaining causes, choosing experiments, or closing a task:

- `Fact`: observed evidence only.
- `Hypothesis`: a possible explanation, candidate cause, or proposed approach that is not yet proven.
- `Decision`: the next action chosen from facts or explicitly marked hypotheses.
- `Verification`: evidence that proves, disproves, or narrows a hypothesis or acceptance claim.

Controlled Exploration may use brainstorming hypotheses when the plan has real uncertainty. The rule is separation: do not present a hypothesis as a conclusion, do not use it as accepted evidence, and do not hide unresolved hypotheses. If a hypothesis matters to acceptance, verify it first. If it remains unverified, record it under `Unverified Items`, `Residual Risks`, or next experiment plan.

## Evidence Capture

For UI or runtime-visible work:

- Capture screenshots, logs, command output, or saved artifacts when they materially support acceptance.
- Name the product path exercised.
- Mention viewport, route, account/data fixture, or environment when relevant.
- Do not substitute DOM/source checks for available product-path behavior.

For automated tests, confirm the command actually ran at least one relevant test. A command that exits successfully with `Ran 0 tests`, `0 passed`, no collected tests, or an empty filtered selection is not validation evidence; treat it as `unverified` or fix the command/test runner before claiming coverage.

Branch coverage map: use `branch-map --json` when reviewing whether idea-to-code branch closure is visible. The map mirrors the branch closure checks in `workflow.md` and lists lifecycle branches with `id`, `workflow_branch`, `entry`, `exit`, `validation`, and `failure_handling`. Treat it as an observability/self-check contract; live compliance still requires actual bundle state, role evidence, validation output, and final verify.

## Generated Test Evidence

When idea-to-code generates tests or validation scripts, evidence must identify ownership:

- `persistent-product-test`: kept in the project test suite.
- `project-native-test`: kept in the project test suite using the project's native framework or layout.
- `task-evidence-only`: kept under `.idea-to-code/<slug>/artifacts/` and not treated as a permanent product test.

Each evidence entry must include `Test Ownership`, `Test file`, covered REQ IDs, and `Validation Type`. Persistent or project-native generated tests must include `idea_to_code` or the task slug in the path/name unless the project already has a clearer local convention. Task-evidence-only files must stay under `.idea-to-code/<slug>/artifacts/`.

## Acceptance Check

Before accepted closeout, confirm:

- implementation exists in the repository
- intake gate is resolved with `Need Confirmation: no`
- Controlled Exploration is either skipped with a concrete Trigger or resolved with options and one decision
- Exploration Visibility Gate output was surfaced before READY and has a current `EXPLORATION_OUTPUT_ID`
- if exploration was revised, the current output shows `Required Now`, `Deferred`, `Rejected Options`, `New / Selected Option`, and `What READY Will Cover`
- the chosen decision fits the user's real goal and does not blindly follow a flawed requested implementation
- the plan recommends one default path instead of dumping unresolved options on the user
- when Controlled Exploration selected an option, validation and review checked whether the decision reason and verification path held up
- recommendation quality is evidenced by user-goal fit, risk/cost reduction, constraint and non-goal preservation, and verifiability
- small-task friction remains a hard guardrail: clear single-path tasks do not gain unnecessary exploration, option dumping, or routine confirmation
- the workflow used no extra confirmation layer beyond the existing Intake Gate confirmation
- acceptance matrix is concrete
- Role Execution Mode is recorded as `same-agent`, `hybrid-team`, or `independent-team`
- same-agent fallback or independent Validator/Reviewer evidence is explained
- the final behavior matches the restated user goal and observable user outcome
- acceptance examples pass and counterexamples of wrong-but-working behavior are not accepted
- non-goal boundaries and user-requested exclusions are respected
- all open REQs are covered
- role evidence is current for the current `plan_revision`
- validation types are named
- generated tests or evidence scripts have ownership, path, covered REQs, and validation type recorded
- real product-path evidence exists when locally available
- risks and deferred work are explicit
- pre-close `verify` passed after Reviewer evidence
- Closer evidence was recorded after pre-close verify
- final `verify` passed after finalize

Use `accepted-with-followup` or `not-accepted` when the evidence does not support full acceptance.

## User-Intent Acceptance Check

Treat user-intent fit as first-class evidence. Before `accepted` closeout, the final report and console response should answer:

- What did the user ask for in implementation terms?
- What observable outcome now proves that request is satisfied?
- Which acceptance examples were exercised?
- Which counterexamples or wrong-result cases were rejected?
- Which non-goals or exclusions were preserved?
- If Controlled Exploration selected a path, what evidence showed the recommendation quality was better than the rejected options?
- Did validation cover the chosen option's decision reason and verification path?
- If the result is only partially aligned, why is it `Progress`, `Blocked`, `partial`, `accepted-with-followup`, `fail`, or `not-accepted`?
- If the user proposed an implementation, did the final decision follow it for good reasons or replace it with a better recommendation?
- Did the agent ask for confirmation only where a true product, security, data, cost, or architecture fork existed?

If a result is technically working but solves a different problem than the user asked for, it is not accepted.

## Role Independence Check

Before accepted closeout, disclose the role execution mode:

- `same-agent`: explain why subagents were unavailable, unnecessary, or riskier than sequential same-agent gates; Reviewer evidence must say `same-agent review`.
- `hybrid-team`: name the independent Validator or Reviewer role and summarize that subagent's evidence.
- `independent-team`: name the independent role/slice ownership and summarize each independent result.

Independent review is stronger because it reduces implementation-confirmation bias, but it must be real. Do not claim an independent agent ran unless the tool call or returned result exists.

For subagent evidence, include the delegation health check or recent successful subagent result, the delegated scope, the agent id/name when available, and whether the result returned before timeout. A timed-out or closed-without-result subagent is a risk record, not validation or review evidence.

Machine-backed delegation evidence uses:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" delegation record --root "$(pwd)" --slug <slug> --role <role> --status usable --scope "<scope>" --evidence-summary "<summary>" --agent-id "<id>"
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" delegation resolve --root "$(pwd)" --slug <slug> --id <DELEGATION_ID> --resolution fallback-same-agent --reason "<why this closes the finding>"
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" delegation status --root "$(pwd)" --slug <slug>
```

Use `status usable` only when a real delegated or fresh-agent run returned usable evidence. Use `timeout`, `unusable`, `planned`, or `unverified` for attempts that cannot support an independent claim. Role evidence that says `independent review`, `subagent`, `fresh-agent`, `hybrid-team`, or `independent-team` must have a current usable delegation record; otherwise it is refused or reported as unverified.

Non-usable delegation records are open findings, not permanent dead ends. Resolve them only after the fallback is explicit, such as `fallback-same-agent`, `superseded`, `accepted-risk`, or `invalid-record`. Resolution means the branch is closed and visible; it does not make the attempt usable evidence.

Do not turn fallback into root-cause proof. If a broad delegation times out but a ping or scoped review succeeds, the only proven facts are those outcomes. The broad timeout cause remains `unverified` until comparison tests isolate it. Record unknown causes explicitly instead of saying the issue was prompt size, queue latency, tool health, or model behavior without evidence.

## Weakness Report Taxonomy

`SKILL.md#Risk And Weakness Taxonomy` is the top-level contract for this rule.

When reviewing skill architecture, process gaps, or a list of "what is still weak", every weakness must include one status label:

- `already hardened`: rules, commands, tests, or installed behavior already address the issue; mention the evidence and do not present it as new work.
- `residual risk`: the issue was hardened but still cannot be fully prevented by the current skill/runtime, such as a tool-layer bypass that scripts can detect but not physically block.
- `new gap`: the issue has no current rule, command, test, benchmark, or state path.
- `external validation`: the rule or artifact exists, but real fresh-session, multi-agent, user acceptance, or environment validation has not been run.

Each weakness must also state the enforcement boundary:

- `repo-enforced`: repository code, tests, CLI commands, or committed artifacts enforce the behavior.
- `skill-enforced`: skill rules and bundle verification require the behavior, but agent cooperation is still part of the control.
- `host-required`: the remaining guarantee needs Codex host/tool support and must not be reopened as a repo-only TODO without a new host integration path.

Reviewer output that repeats a prior weakness without one of these labels is ambiguous. Before turning such a weakness into a new TASK, map it to the earlier evidence or mark it as a new gap with a concrete reason.

## Console Response Check

Formal tracked handoff validation treats the final assistant message as the artifact under test. The command output that generated `render-status` is supporting evidence only. A closeout is noncompliant when `tool_stdout` contains a valid `render-status` block but `assistant_visible_body` omits it, summarizes it casually, or drops fixed fields.

Use the output compliance helper when checking this failure mode:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" output-compliance check --kind formal-status --tool-stdout-file <render-status-output.txt> --assistant-body-file <final-message.txt>
```

The helper must fail when the final body does not start with `[idea-to-code][Closer/agent] Status: Completed|Progress|Blocked`, omits any fixed field, drops TASK/REQ mapping, moves `No commit made` under `Incomplete Items`, or loses `EXPLORATION_OUTPUT_ID` / `READY_TASK_OUTPUT_ID` that were present in `render-status`.

For final closeout of tracked work, run this check whenever the assistant-visible final body is available as text before handoff or review. If the host cannot expose the final body before sending, record that as `host-required` rather than silently skipping the check. Running `render-status` alone is generation evidence; passing `output-compliance check --kind formal-status` is body-compliance evidence.

## READY Visibility Check

## Exploration Visibility Check

Before READY and before product-file edits, the Controlled Exploration decision must be visible to the user in a normal assistant message, not only command stdout, tool output, folded transcript, or internal notes.

Use:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" exploration render --root "$(pwd)" --slug <slug>
```

For `Need Confirmation: no`, the output must be `Exploration Result` and include `EXPLORATION_OUTPUT_ID`, `Display Layer`, `Next Layer`, `Planned Scope`, selected approach, why it was chosen, and that implementation proceeds to READY. It must not ask for routine approval.

For `Need Confirmation: yes`, the output must be `Confirmation Required` and include `EXPLORATION_OUTPUT_ID`, `Display Layer`, `Next Layer`, `Planned Scope`, `Decision Options`, a recommended option, and reply choices including `approve`, `choose: <option>`, `change: <correction>`, `explore more: <direction>`, `pause`, and `cancel`.

When the user revises exploration, the next output must use a new `EXPLORATION_OUTPUT_ID` and show `Required Now`, `Deferred`, `Rejected Options`, `New / Selected Option`, and `What READY Will Cover`. If the user only provides a direction for more exploration, keep the output as `Confirmation Required` with new candidate options; do not treat the direction as a selected route. Deferred scope must not appear in READY except as deferred/follow-up context, and rejected options must not remain the default route.

`implementation ready` may print Exploration Visibility Gate output before READY when it must refresh the output. That does not remove the user-visible message obligation. If the output was missing before earlier edits, later printing is remediation only and must be recorded as noncompliance.

For large ideas, keep Exploration Visibility Gate output separate from READY. Exploration explains the selected approach; focused READY excerpts explain the next TASK. Future grouped READY summaries may reduce visual clutter, but cannot replace focused TASK/REQ execution visibility.

Before product-file edits, the READY task list must be visible to the user in a normal assistant message, not only command stdout, tool output, or a folded transcript.

Use the output compliance helper when checking the exact distinction between generated tool output and visible assistant output:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" output-compliance check --kind ready --tool-stdout-file <ready-command-output.txt> --assistant-body-file <assistant-ready-message.txt>
```

The helper must fail when `Exploration Result` or `Implementation Gate: READY` exists only in `tool_stdout`, or when the visible body omits `Required Now`, `Deferred`, `Selected Option`, `What READY Will Cover`, `Files`, `Execution Details`, `Done Criteria`, or `Planned Verification`.

READY visibility has two layers:

- `Plan-level READY`: the complete TASK list remains in `00-idea.md`; use `implementation ready --full-plan` or `implementation show-ready --full-plan` when full READY output is needed for traceability.
- `Execution-level READY`: the current TASK excerpt is shown immediately before that TASK is executed.

For multi-task work, default user-visible execution display to the current TASK's focused READY excerpt, not the full long TASK list. `implementation ready` and `implementation show-ready` default to the first TASK/IMP focused excerpt; before moving from one TASK to the next, show the next TASK's focused READY excerpt unless the user explicitly asks to skip repeated visibility. Every current TASK transition needs visible task info for that TASK before edits begin, not just one full list at the beginning.

Use `implementation enter-task --task <TASK-ID>` as the normal transition command. It records `current_task_id`, preserves the current `READY_TASK_OUTPUT_ID`, and prints `Display Layer: READY Focus`. Use `implementation overview` for read-only progress questions; it must show `Planned Scope`, current TASK, next TASKs, and the `--full-plan` audit hint without mutating implementation evidence.

Use the READY task filter when a long bundle would hide the current work:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation show-ready --root "$(pwd)" --slug <slug> --task TASK-17
```

Focused READY output is for user visibility only. It does not change bundle scope, requirements, gate state, or role evidence expectations. The output should identify `Display Layer: READY Focus`; full audit output should identify `Display Layer: Full Plan`.

READY output must also show the trace hierarchy and implementation granularity. The required hierarchy is `IDEA-* -> REQ-* -> TASK-* -> optional IMP-*`. Use `Implementation Granularity: task-only` when the visible plan has no `IMP-*` blocks, and `Implementation Granularity: task+imp` when it does. This is an additive visibility rule, not a new mandatory layer: missing `IMP-*` in task-only work is acceptable, but missing `TASK-*` or `REQ-*` visibility is still a flow-control failure.

Visibility evidence requires meaningful content, not just IDs. A valid execution handoff before tracked edits shows the Exploration summary fields (`Required Now`, `Deferred`, `Selected Option`, and `What READY Will Cover`), `Implementation Granularity`, `Trace Hierarchy`, plus the focused TASK fields (`Files`, `Execution Details`, `Done Criteria`, and `Planned Verification`). Tool stdout, folded transcripts, internal notes, `EXPLORATION_OUTPUT_ID`, or `READY_TASK_OUTPUT_ID` alone do not prove the user saw the scope.

Friendly display is the compact required block, not a prose substitute. A line like `Exploration Result: Required Now = ...` or `READY Focus TASK-2 / REQ-2: files are ...` may be useful context, but it is not compliant gate visibility unless the same assistant-visible message also contains the required `Display Layer` block fields. Keep the block short by using focused READY, but do not collapse it into a single sentence.

## Output Acceptance Gate

When a TASK changes lifecycle display, output compliance checks, READY or Exploration formatting, final status formatting, role/source prefixes, language-boundary behavior, or ordinary-answer boundaries, validation must include the output acceptance gate before the TASK can be accepted:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" output-compliance self-test --json
```

The self-test must pass from the source copy and, after installation, from the installed skill copy when the skill itself changed. Focused output tests must also pass.

When a real transcript or exported conversation is available, validation must also audit the actual visible flow:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" output-compliance transcript-audit --transcript-file <path> --json
```

This audit is required evidence for output-rule or lifecycle-display changes because self-tests only prove constructed fixtures. Transcript audit must fail closed when `Exploration Result`, `Implementation Gate: READY`, or `render-status` appears only in tool stdout, folded transcript output, or one-line summaries while the assistant-visible body lacks the required Display Layer or fixed status fields. If a real transcript shows malformed hard output, the TASK must remain incomplete until the output path is fixed and the transcript audit is rerun.

The JSON result includes `backlog_hits` when the audit can map observed output failures to the master backlog. Validation must use those IDs explicitly: covered IDs belong in the current TASK/REQ evidence; uncovered IDs remain in Remaining Backlog / Next Batch. A passing source fixture is not enough when a real transcript still reports `backlog_hits` for in-scope failures.

Reviewer evidence must say whether a clean subagent/fresh-agent style review ran. If such a clean review is available and reports malformed hard output, hidden tool-only output, missing Display Layer fields, or ordinary-answer over-templating, the TASK must remain incomplete until fixed. If no clean review tool or no real transcript artifact is available, record that as `Unverified Items`; do not claim independent, fresh-agent, or live-transcript validation.

When `00-idea.md` changes after Exploration or READY output is generated, the old IDs are stale. Execution gates should refuse until the agent refreshes Exploration/READY and surfaces the refreshed blocks to the user.

The generated READY output has a hard excerpt contract. Every visible TASK/IMP block must include:

- `Implementation Granularity`
- `Trace Hierarchy`
- the `TASK-*` or `IMP-*` line
- covered `REQ-*` or the script's covered REQ hint when inferable
- `Files`
- `Done Criteria`
- `Planned Verification`

If generated READY output omits any of these fields, it is invalid. Regenerate or fix the parser/formatter before product-file edits; do not treat a folded transcript, partial copy, or field-only snippet as sufficient READY visibility.

Closed-loop verification should check both human-visible output and machine state: after `enter-task`, `implementation status` should expose the same current TASK ID that was shown in READY Focus.

Before tracked implementation edits, acquire a write lease for the current TASK files:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug <slug> --task <TASK-ID> --owner <owner> --file <path>
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation lease acquire --root "$(pwd)" --slug <slug> --task <TASK-ID> --owner <owner> --files <path-a> <path-b>
```

The lease is valid only for the current plan revision and READY output. Use repeated `--file` for compatibility or grouped `--files <path>...` for multi-file TASKs; prefer grouped `--files` when it keeps guard evidence concise. Overlapping active leases for different owners are refused, so parallel workers cannot silently claim the same file. Same-agent implementation still uses a lease so pre-edit behavior is consistent. `implementation lease status` must expose active and released leases, and finalize must close remaining active leases so completed bundles do not appear to retain live write ownership. Validator/Reviewer/read-only subagents do not need a write lease unless they edit files.

Before tracked repository or artifact edits, run the machine pre-edit guard after `enter-task` and before the file-editing tool:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug <slug> --task <TASK-ID> --file <path>
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" implementation pre-edit --root "$(pwd)" --slug <slug> --task <TASK-ID> --files <path-a> <path-b>
```

The guard must print `PRE_EDIT_OK_ID`. It is valid only for the current bundle, current Exploration Visibility Gate output, current READY output, current TASK entry, and the files listed under that TASK. Use repeated `--file` for compatibility or grouped `--files <path>...` for multi-file TASKs. If it refuses, do not edit; refresh the failed gate or fix the plan first.

Closed-loop verification should check that `implementation status` exposes `pre_edit_ok_id`, `pre_edit_task_id`, `pre_edit_files`, and `pre_edit_records` after a passing guard. Implementer evidence must cite the current `PRE_EDIT_OK_ID` when one exists for the current plan revision, and the guard records must cover every file claimed for the current TASK. Missing, stale, wrong-task, or incomplete guard coverage is a verification problem, not a cosmetic warning.

If an edit can be represented as a git patch, use `implementation guarded-apply --task <TASK-ID> --patch-file <path>` as the default tracked edit path so the wrapper checks patch paths, active READY/current TASK state, lease coverage, and pre-edit before applying. If a tracked edit cannot use `guarded-apply`, Implementer evidence must state the fallback reason and still cite the current `READY_TASK_OUTPUT_ID` and `PRE_EDIT_OK_ID`; fallback edits are not wrapper-compliant evidence. If an edit happened before the guard, record it with `implementation noncompliance --task <TASK-ID> --reason "<reason>" --file <path>`. Open pre-edit noncompliance must be listed by `implementation status`, `verify`, and `render-status`; it cannot be moved only to Key Technical Details or omitted from formal tracked status.

Tool-layer edit wrapper design: the future enforcement target is a tracked-edit wrapper or host pre-edit hook that physically sits before file writes. It must resolve the active bundle, confirm the visible Exploration Visibility Gate output and READY Focus for the current TASK, verify or acquire a non-overlapping lease, run `implementation pre-edit`, reject writes outside the TASK file scope, capture `PRE_EDIT_OK_ID`, and require Implementer evidence to cite that same guard after the write. Current Codex edit tools are not physically blocked by the skill itself, so the absence of that wrapper is a `residual risk`; do not describe current guidance as non-bypassable physical enforcement.

The final formal `Progress` or `Completed` response must map `Changes`, `Completed Items`, `Incomplete Items`, and `Validation Results` back to the same visible Exploration Visibility Gate output plus TASK/REQ set for single-idea sessions, and to the same visible IDEA/TASK/REQ set when a session ledger contains multiple ideas. For single-idea sessions, TASK/REQ mapping plus the current `EXPLORATION_OUTPUT_ID` is enough when the idea scope is unambiguous.

For same-session related follow-ups, final or status responses must also map back to the prior related session scope, not only the newest bundle or most recent local edit. If the user asks whether "everything", "the earlier issue", "the 1-7", or "what we discussed" is complete, first audit the prior related scope and state what is covered, deferred, superseded, or unverified. If unrelated, keep the answer ordinary and do not invent bundle accounting.

Material same-session follow-ups should be recorded with:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" session audit --root "$(pwd)" --slug <slug> --relation <same-scope|scope-correction|new-related-scope|unrelated> --summary "<summary>" --prior-scope "<prior scope>" --decision "<decision>"
```

`session status`, `implementation status`, and `render-status` expose the latest audit so long conversations and compacted context can be re-anchored to state-backed scope records.

Material same-session ideas that need durable continuity should also be recorded with:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" idea record --root "$(pwd)" --slug <slug> --id IDEA-1 --status active --summary "<English idea summary>" --related-reqs "REQ-1,REQ-2" --notes "<English trace notes>"
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" idea status --root "$(pwd)" --slug <slug>
```

Use `idea record` when the user introduces, corrects, rejects, defers, completes, blocks, or reopens a material idea. The fields are English-only ASCII so bundle state stays portable; user-facing explanation may still use the user's language. Formal tracked status with multiple idea records must map meaningful result bullets to IDEA/TASK/REQ.

Material follow-ups that could be same-scope, scope-correction, new-related-scope, or unrelated should be classified with:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" scope classify --root "$(pwd)" --slug <slug> --classification <same-scope|scope-correction|new-related-scope|unrelated> --summary "<summary>" --rationale "<rationale>" --action "<action>"
```

`scope status`, `implementation status`, and `render-status` expose the latest classification. A related correction without a classification is a traceability gap; an unrelated ordinary answer should not be forced into TASK/REQ accounting.

If the tracked scope came from a numbered issue list, the final response must preserve those original IDs or include a mapping table with `Previous ID`, `Current ID`, and `Change Reason`. Do not claim "1-7 completed", "item 3 fixed", or similar status unless the response maps to the same numbered meanings that were shown in Exploration/READY. If a later answer used a different numbering, record it as traceability noncompliance and correct the mapping before claiming progress.

If the tracked scope has a master backlog, validation and final status must include the persisted `MB-*` state from `backlog status` or `implementation status`. `Completed` for a response-scoped slice does not mean the whole master backlog is complete; incomplete MB IDs must appear in `Incomplete Items` or `Unverified Items` unless they are explicitly deferred.

Compressed master backlog ranges must be expanded before acceptance. Validation should reject state where `MB-6..MB-19` leaves out `MB-7..MB-18`; use `backlog status` or `render-status` to confirm every intermediate `MB-*` remains visible.

Deferred MB items are still remaining work. When a formal tracked result closes one batch of a larger backlog, `render-status` must surface `Remaining Backlog` and `Next Batch` in the fixed-field response details until every MB item is `completed` or `covered`. Do not hide deferred next-batch work merely because the current TASK has no incomplete items.

For multi-task or multi-idea work, "same visible IDEA/TASK/REQ set" means each result bullet maps to the focused execution-level READY excerpt shown before that TASK and to the relevant IDEA scope when more than one idea exists in the session. The final summary may aggregate TASKs, but it must not introduce unshown or unmapped work.

The final user-visible console/chat response is a closeout artifact. Use the fixed field contract only for formal tracked delivery status: final closeout, blocked handoff, review handoff, keep/revise/rollback handoff, or when the user explicitly asks for progress, completion, summary, validation, or commit/publish state for work that entered todo/REQ/TASK accounting. For tracked delivery-status work, it must start with an idea-to-code role/source prefix such as `[idea-to-code][Closer/agent]` and use these field names:

Language boundary: entries from `SKILL.md#Protocol Glossary / Do-Not-Translate List` stay English-only ASCII. This includes fixed field names, role/source prefixes, role names, IDs, commands, evidence strings, validation types, and bundle state. The meaningful explanation around those fields, including caveats, interpretation, recommendations, and conclusion, should follow the user's language by default.

- `Status`
- `Changes`
- `Completed Items`
- `Incomplete Items`
- `Validation Results`
- `Unverified Items`
- `Residual Risks`
- `Key Technical Details`

Before sending formal tracked delivery status, run the read-only `render-status` helper whenever it is available:

```bash
python "$HOME/.codex/skills/idea-to-code/scripts/idea_to_code_bundle.py" render-status --root "$(pwd)" --slug <slug> --status Completed|Progress|Blocked
```

The helper does not finalize, verify, or mutate the bundle. It emits a fixed-field skeleton with TASK/REQ placeholders, `EXPLORATION_OUTPUT_ID`, `READY_TASK_OUTPUT_ID`, and default no-commit placement under `Key Technical Details`. When milestone, IDEA ledger, backlog, session, scope, delegation, or noncompliance evidence exists, the helper should surface that evidence directly and keep placeholders only where evidence is genuinely missing. Formal tracked status MUST use render-status generated fields when the helper is available: replace placeholders with actual evidence before sending, but do not omit, rename, reorder, or hand-invent the fixed field set. If `render-status` is unavailable or fails, state that reason and manually use the same fixed fields. Do not omit fields, do not drop TASK/REQ mapping from `Changes`, `Completed Items`, `Incomplete Items`, or `Validation Results`, do not drop IDEA/TASK/REQ mapping when multiple ideas exist in the session ledger, and do not move no-commit state into `Incomplete Items`. Do not use it for ordinary untracked answers.

Allowed status labels are `Completed`, `Progress`, and `Blocked`. Status labels describe the scope of the current user-visible response. In session-ledger mode, state or imply the active scope, such as `Scope: IDEA-2 / TASK-4 / REQ-7`, whenever multiple ideas exist. Use `Completed` when every IDEA/TASK/REQ in that response's stated scope is implemented and validated. If `Incomplete Items` is `none` for the stated response scope and validation passed, default to `Status: Completed`; do not downgrade to `Progress` only because the session ledger remains open, no commit was made, fresh-session retest remains external, or user acceptance has not been separately collected. For an interim IDEA/TASK/REQ slice, `Completed` does not claim the whole session ledger is finalized, accepted, committed, or published; disclose those facts under `Key Technical Details` or `Unverified Items`. Use `Progress` when at least one in-scope IDEA/TASK/REQ is still being implemented or validated. Use `Blocked` when in-scope work cannot continue without an external dependency or decision. If there are no incomplete items, unverified items, or residual risks, write `none` under those fields instead of omitting them.

Do not use `Completed` to claim final accepted closeout for the whole bundle until accepted closeout is supported by current role evidence, pre-close verify, finalize, and final verify.

For formal tracked `Progress`, validation, install, or status responses, require TASK/REQ mapping in the user-visible bullets:

- `Changes`: name the relevant `TASK-*` and `REQ-*`.
- `Completed Items`: name the completed `TASK-*` and covered `REQ-*`.
- `Incomplete Items`: name only unfinished in-scope `TASK-*` or `REQ-*`, or write `none`.
- `Validation Results`: name the checked `TASK-*`/`REQ-*`, validation type, command/evidence, and result.

When the session ledger contains multiple ideas, the same bullets must also name or clearly imply the relevant `IDEA-*` scope. A formal tracked response that cannot map each result bullet to TASK/REQ, or to IDEA/TASK/REQ for multi-idea session ledgers, is noncompliant and must be regenerated from `render-status` or corrected before sending.

Do not report substantial check/install/validation work as tracked Progress unless that work was represented by a READY TASK before the report. If the user asks an ordinary explanation question, do not invent TASK accounting just to use the fixed template.

Do not list `No commit made`, `bundle not finalized`, `awaiting user review`, or fresh-session/user acceptance retest as `Incomplete Items` unless commit, finalize, review, or retest is itself an explicit in-scope TASK/REQ. Put no-commit and bundle-finalization state in `Key Technical Details`; put fresh-session checks, user acceptance, or other external checks in `Unverified Items`.

If tracked local changes have not been committed, explicitly state `No commit made` in `Key Technical Details` unless commit was an explicit in-scope TASK/REQ and is therefore genuinely unfinished. Do not leave commit/publish state implicit.

### Installed Skill Parity Checklist

When tracked work changes the idea-to-code skill itself and the user expects the latest code to be installed, installation is a validated TASK/REQ activity, not a copy-only statement. Formal install, validation, or final status must name the relevant TASK/REQ and show:

- install target path, normally `$CODEX_HOME/skills/idea-to-code`;
- installed focused tests executed against the installed copy or installed script path;
- source/installed SHA256 parity for every changed skill file included in the batch;
- `No commit made` under `Key Technical Details` when commit was not requested or performed.

If any installed focused test or source/installed SHA256 parity check is missing or failing, the response must not claim "latest skill installed and verified." Report the gap in `Unverified Items` or in the incomplete TASK/REQ that owns installation evidence.

Do not use the fixed field contract for ordinary questions, short explanations, naming discussions, quick clarifications, or lightweight commentary updates, even when a bundle is active. These replies should stay concise and natural while still using the role/source prefix; the template is for formal tracked delivery status, not every message. The boundary is semantic: if no tracked delivery status, install, validation, commit, blocked handoff, review handoff, keep/revise/rollback decision, or final status is being reported, answer naturally and do not add READY, `render-status`, or fixed fields just because a bundle exists.

For ordinary-answer regression checks, use `output-compliance check --kind ordinary` to fail outputs that add READY, `render-status`, or fixed status fields to explanation-only responses.

Mixed-response split rule: if the user asks both a tracked status question and an ordinary review/evaluation question in the same message, split the answer instead of creating a new fixed template. The status portion should be one concise sentence with relevant TASK/REQ IDs, validation/install state, and `No commit made` when relevant. The review portion should be natural prose in the user's language with lightweight headings such as current strengths, current gaps, and suggested TODO. Do not run or paste full `render-status` fields for the review portion, and do not add a second fixed response template to solve this case.

Review-discovered TODO capture rule: when natural review or formal review identifies a `new gap`, the response must say whether it is a suggested TODO, a proposed REQ/TASK for the next bundle, deferred, or rejected. A `new gap` cannot disappear from the next planning step, and it cannot be counted as completed unless a tracked TASK/REQ and validation evidence cover it. If the user says to continue, convert accepted TODO candidates into explicit REQ/TASK scope before implementation.

### Response Mode Check

Before a user-facing response at the end of a turn, choose the output shape:

| Response situation | Output shape |
|---|---|
| Formal tracked delivery status or final handoff | Fixed fields. |
| Mixed tracked status plus ordinary review/evaluation | Concise tracked status sentence, then natural review sections. |
| Ordinary question/explanation/naming discussion | Natural concise answer. |
| In-progress commentary update | Short action-oriented update. |

If uncertain, use fixed fields only when the user needs formal tracked delivery status. Otherwise answer naturally and concisely.

## Confirmation Handoff Check

When `Need Confirmation: yes`, the user-visible response is also a gate artifact. It must not look like a normal progress update. Check that it includes:

- `[idea-to-code][Planner/agent] Confirmation Required`
- why implementation is paused
- the proposed scope after approval
- exact accepted replies such as `yes`, `approved`, `change: <correction>`, `pause`, and `cancel`
- what happens next after approval

If the user cannot tell how to answer from the message itself, the confirmation request is incomplete.
