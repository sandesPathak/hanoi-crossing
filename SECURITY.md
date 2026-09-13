# Security

## What this program is

A local, offline command-line program. It reads a game transcript from a file or stdin,
runs a deterministic simulation, and writes a result to stdout. It opens no sockets,
writes no files, spawns no subprocesses, and has no authentication, persistence or
multi-tenancy.

That narrow shape is the main control. Most of the policy below exists to keep it that way.

## Trust boundary

There is exactly one: **the transcript supplied by the caller is untrusted input.**

Everything else — the engine, the frontends, the test fixtures — is trusted code. A
reviewer looking for the risky surface should look at the transcript parser and nowhere
else.

### Threats considered

| Threat | Response |
| --- | --- |
| Deserialisation leading to code execution | JSON via the standard library only. `pickle`, `marshal`, `yaml.load`, `eval` and `exec` are banned and the ban is lint-enforced. |
| Resource exhaustion via a hostile transcript | Hard caps on input size, disk count and move count, checked before simulation begins. |
| Path traversal | The transcript is data. It never names a path, and the program never opens a file the caller did not pass on the command line. |
| Untrusted data reaching a shell | No `subprocess`, no `os.system`, no shell interpolation anywhere. |
| Terminal escape injection via output | Values echoed back to stdout are validated, and identifiers are constrained to a known alphabet rather than passed through. |

### Explicit non-goals

Sandboxing against a hostile *operator*. Someone who can run this binary can already run
Python; the program defends the caller's data, not the machine from its caller.

## Supply chain

- **No runtime dependencies.** `[project].dependencies` is empty and a test asserts it
  stays empty. Nothing third-party is present at runtime, so nothing third-party can be
  compromised at runtime.
- Development tooling is locked in `uv.lock`, which is committed. CI runs with
  `UV_FROZEN=1`, so a build fails rather than silently resolving something new.
- `pip-audit --strict` runs in CI against the locked set.
- GitHub Actions are pinned to full commit SHAs, not tags. A tag can be moved; a SHA
  cannot. Dependabot raises the updates.
- CI grants `permissions: contents: read` at the workflow level; no job requests more.
- `gitleaks` scans the full history in CI and every commit locally via `pre-commit`.

## Static analysis

`ruff` runs with the `S` (flake8-bandit) rule set enabled across `src` and `tests`, so the
bans above fail the build rather than relying on review to catch them. `mypy --strict`
runs over the same tree.

## Reporting a vulnerability

Open an issue, or email pathaksandesh025@gmail.com. This is an interview exercise rather
than deployed software, so there is no formal SLA.
