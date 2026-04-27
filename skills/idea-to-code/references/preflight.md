# Preflight Checks

## Purpose

Before running the delivery loop, confirm the workspace is actually ready to implement and verify. Catch broken baselines here so they don't get misattributed to your changes later.

## Checklist

0. **Check for orphan long-running processes from earlier sessions.** If the project opens a server port (TCP/UDP) or holds a lock, stale processes from a prior session will silently accept connections with pre-edit code — symptom: "I edited X, tests pass in-process, but end-to-end behavior is wrong as if my edit never happened." See *Orphan Process Check* below.
1. **Locate the project root.** Use `pwd`. All bundle commands pass `--root "$(pwd)"` so they write to the right place.
2. **Detect the stack.** Look for one of these markers:
   - `package.json` (Node/TS/JS: React, Vue, Angular, Svelte, Next, Nuxt)
   - `pyproject.toml` / `setup.py` / `requirements.txt` (Python)
   - `Cargo.toml` (Rust)
   - `go.mod` (Go)
   - `pom.xml` / `build.gradle` (Java/Kotlin)
   - `*.csproj` / `*.sln` (C#/.NET)
3. **Record build + test commands** (write them in your head or in `02-prd.md > Technical Shape`):
   - Build: `npm run build` / `cargo build` / `dotnet build` / `pytest --collect-only` / etc.
   - Test: `npm test` / `cargo test` / `pytest` / `go test ./...`
4. **Confirm baseline builds.** Run the build once **before** making changes. If it fails on untouched code, ask the user before proceeding — this is one of the explicit stop conditions in the autonomy rules.
5. **Confirm the bundle directory is writable.** `.idea-to-code/` sits in the project root; a read-only workspace or wrong cwd will surface here first.
6. **Confirm Python 3.8+ is available.** `python --version`. If `python` isn't on PATH, try `python3`; use whichever is present in subsequent calls.

## Preflight Failure Handling

| Problem | Action |
|---|---|
| Unknown / unrecognized stack | Ask the user for the stack and expected build/test commands. |
| Baseline build fails due to **stale generated artifact** (see below) | Auto-fix. Do NOT ask. Report what you reset in the milestone notes. |
| Baseline build fails on **source-level errors** you didn't write | Report the failure, do NOT implement first. Ask whether to fix the baseline or proceed. |
| Required toolchain version too old on `PATH` but a newer one exists in a standard location | Use the newer one. Report the path in the first milestone and tell the user they can upgrade the system `PATH` version if they want. Do NOT ask for permission first. |
| No write access to `.idea-to-code/` | Report the path and permissions issue, do NOT fall back to a different location silently. |
| Python missing | Report it — the delivery bundle cannot be used, but the actual coding/verification work can still proceed. Tell the user. |
| Project has no test command and no test framework | Note it in the milestone's `--verified` field as "no automated tests, <runtime check run>". Use `--gate-status partial` unless a meaningful runtime check was executed. |

### Stale Generated Artifacts — Safe To Reset Without Asking

These are auto-generated build byproducts, not the user's work. Deleting and regenerating them is safe:

- `build/` directory with a stale `CMakeCache.txt` pointing at a moved/renamed source tree (classic "CMAKE_SOURCE_DIR changed" error) — delete `build/`, re-run `cmake -S . -B build`.
- `node_modules/` when `package-lock.json` shows a dependency mismatch — `rm -rf node_modules && npm ci` (only after reading the lockfile; don't do this if there's no lockfile).
- `__pycache__`, `.pyc`, `target/` (Rust), `bin/` + `obj/` (.NET), `out/` (generic) when they contain output from a different commit.
- `.next/`, `.nuxt/`, `.turbo/`, `dist/` when a previous build left incompatible output.

Rule: if the artifact is in `.gitignore` or lives under a conventional build output directory, treat it as disposable environment state. If it's source, asks.

### Common Alternative-Toolchain Paths (Windows)

When `PATH` has an outdated version, try these before asking the user to upgrade:

- CMake: `C:\Program Files\Microsoft Visual Studio\<year>\<edition>\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe`
- MSBuild: `C:\Program Files\Microsoft Visual Studio\<year>\<edition>\MSBuild\Current\Bin\MSBuild.exe`
- Node / npm: Check `%LOCALAPPDATA%\Volta\bin\` if Volta is installed; nvm-windows typically under `%APPDATA%\nvm\<version>\`.

macOS equivalents: Homebrew under `/opt/homebrew/bin/` (Apple Silicon) or `/usr/local/bin/` (Intel); Xcode-bundled tools under `/Applications/Xcode.app/Contents/Developer/usr/bin/`.

Linux: typically `/usr/local/bin/`, or distro-specific SCL paths like `/opt/rh/<toolset>/root/usr/bin/`.

If you use an alt-path tool, record the absolute path in milestone `--delivered` so future sessions know the PATH version is insufficient.

## Orphan Process Check

Before running a TCP/UDP/socket end-to-end test, verify no stale server from a previous session is still bound to the port. This check is cheap and catches a whole class of "my edit didn't land" confusion.

Windows:
```bash
netstat -ano | grep ":<PORT>" | grep LISTENING
# If any PIDs appear: `taskkill //PID <pid> //F`
```

macOS / Linux:
```bash
lsof -nP -iTCP:<PORT> -sTCP:LISTEN
# Or:  ss -ltnp | grep ":<PORT>"
# Kill with: kill -9 <pid>
```

Run this **before each end-to-end round-trip run**, not just at preflight — a background process you started a milestone ago can outlive your own Bash tool's lifecycle.

### Symptom → Cause Table For End-to-End Weirdness

| Symptom | Likely cause |
|---|---|
| Protocol error on a message type you just added | Stale server process from a previous session still running old code |
| TCP test hangs | Port bound by orphan process, new server silently failed to bind |
| Inconsistent results between unit tests and e2e | Only e2e talks to the orphan; in-process tests use fresh imports |
| Message ID / session counter starts at an unexpected high number | Persistent state file reused from prior run; new server loaded it |

## Rule

Preflight is cheap. Skipping preflight turns "the feature broke the build" into a five-minute false alarm.
