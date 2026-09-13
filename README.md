# Hanoi Crossing

A two-player Tower of Hanoi variant. Each player owns three poles and a stack of disks;
the middle pole is shared, visible to both, and either player may take from it. Neither
player can see the other's outer poles or what they are holding.

```
        1a          A's home          A plays 1a -> 3a, B plays 1b -> 3b.
         |                            Pole 2 is the same pole for both of
 1b --- [2] --- 3b                    them: each player's spare peg is
         |                            also the other's, and nobody can win
        3a          A's goal          while anything is left standing on it.
```

A owns the odd disk sizes, B the even ones, so every disk in the game has a distinct size
and the placement rule stays total where the two halves meet.

This repository contains the game engine and two command-line frontends that drive it.

## Status

Complete: engine, both frontends, and 127 tests at 100% coverage.
The commit history is meant to be read in order.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for environment and dependency management

## Getting started

```bash
uv sync --all-groups   # create .venv and install dev tooling
uv run pytest          # run the test suite
```

The engine itself has **no runtime dependencies** — only the standard library. Everything
in `[dependency-groups].dev` is tooling and never ships.

## Playing it

```bash
uv run hanoi-replay examples/brief-example.json     # replay a recorded game
uv run hanoi-random --disks 3 --seed 42             # both players move at random
uv run hanoi-random --games 500 --seed 1            # aggregate over many games
```

The two frontends compose, which is the sharpest check that they agree:

```bash
uv run hanoi-random --disks 2 --seed 42 --emit-transcript | uv run hanoi-replay -
```

## Formats

A transcript is JSON. Turn order and moves are separate lists of equal length: entry `i`
of `turn_order` says who acts on step `i`, and entry `i` of `moves` says what they do.

```json
{
  "version": 1,
  "disks_per_player": 1,
  "turn_order": ["A", "B", "A"],
  "moves": [
    { "action": "lift",  "pole": "1a" },
    { "action": "lift",  "pole": "1b" },
    { "action": "place", "pole": "3a" }
  ]
}
```

Poles use the brief's names: `1a`, `3a`, `1b`, `3b`, and `2` for the shared one. Actions
are `lift`, `place` and `skip`; `skip` takes no pole.

Output is JSON too, listing each pole bottom disk first:

```json
{
  "disks_per_player": 1,
  "turns_played": 3,
  "illegal_actions": 0,
  "outcome": { "kind": "win", "players": ["A"] },
  "final_state": {
    "poles": { "1a": [], "3a": [1], "1b": [], "3b": [], "2": [] },
    "hands": { "A": null, "B": 2 }
  }
}
```

`kind` is `win`, `draw` or `unfinished` — the last meaning the turn order ran out with
nobody having won. That is not a loss for anyone; the game simply did not finish.

## Design decisions

### The engine is a pure function, and agents only ever see an Observation

`step(state, player, action)` returns a new `GameState` and never mutates the one it was
given. There is no session object, no global registry and no hidden clock, so one process
can hold thousands of unrelated games without them interfering. A property test drives
random play and asserts the input state is untouched.

The part that matters more is `Observation`. A player is never handed a `GameState`. They
get their own two poles, the shared pole, and their own hand — and `legal_actions` takes
an `Observation`, not a `GameState`. An RL policy or a remote client can therefore
enumerate its own moves from exactly what the rules say it can see. The random player is
written that way deliberately: it is the same interface an external agent would use, so
the claim that the engine is agent-ready is demonstrated rather than asserted.

Turn order stays outside the engine entirely. `run_match` takes any iterable of players,
so an alternating order, a lopsided one, or a randomly drawn one all work unchanged.

### The win condition is read literally

The brief says a player wins when their hand is empty and, among their visible poles,
only pole 3 has disks. Read literally that does **not** require the disks on pole 3 to be
that player's own, nor all N of them. I kept the literal reading, and it turns out to
matter: in a random game a player often wins with a partial stack, because the other
player carried some of their disks away through the shared pole.

The alternative — requiring all N of a player's own disks on their pole 3 — is a defensible
reading and a one-line change to `has_won`. I went with the text as written.

### Winning is a property of the board, not of your own move

The condition is checked for both players after every action. This is the more faithful
reading of "a player wins when ...", which describes a state rather than an outcome, and
it has a real consequence: because a win needs the shared pole clear, **your opponent can
hand you the game** by lifting the last disk off it. There is a test for exactly that.

### A simultaneous win cannot actually happen

Both players need the shared pole empty. The only way to empty it is to lift from it, and
lifting fills the lifter's hand, which disqualifies them. So no legal sequence produces two
winners at once, and the `draw` outcome is unreachable through play.

The engine still reports it, because `run_match` accepts an arbitrary starting board and a
constructed one can satisfy both. Handling a case the type system permits is cheaper than
arguing it away, and the reasoning above is recorded in the code rather than lost.

### Disks stop belonging to anyone once they reach the shared pole

Placement is decided by size alone. Player A owns the odd sizes and B the even ones purely
so that every disk in the game has a distinct size and the rule stays total where the two
halves meet. A may lift B's disk off the shared pole and put it on their own goal — or bury
it back on their home pole. Nothing in the brief forbids it, and it is the main lever
either player has against the other.

### An illegal action is a wasted turn, not an error

`step` returns the original state with `legal=False` and the driver counts it. Only one
thing raises: applying an action to a game that is already won, which is a caller bug
rather than a move.

`skip` is always legal, so a player is never stuck, and the random player includes it in
its uniform choice. Excluding it would quietly make it a different agent from the one the
rules describe.

### Termination is the frontend's problem

A game can run forever if both players dawdle, so `run_match` stops when the turn order is
exhausted and random play bounds it with `--max-turns` (default 1000). The engine itself
imposes no limit, because an RL loop wants to set its own.

### Bounds live at the trust boundary

Input size, disk count and move count are capped in the parser, before the engine sees
anything. See [SECURITY.md](SECURITY.md).

## Beyond these two frontends

The brief asks that the engine later serve, unchanged, as the core of an RL training loop
or of a service holding many concurrent games — and asks that neither be built. Neither is.
This is what the seam looks like from the outside, and why nothing has to change:

```python
from hanoi_crossing.engine import initial_state, legal_actions, observe, step

state = initial_state(disks_per_player=3)  # reset()
for player in turn_order:  # scheduling stays outside the engine
    obs = observe(state, player)  # the agent's entire world
    action = policy(obs, mask=legal_actions(obs))  # action masking comes free
    result = step(state, player, action)  # pure: a new state, nothing mutated
    reward = 1.0 if player in result.winners else 0.0
    state = result.state
```

Four properties make that work, and each is load-bearing rather than incidental:

- `legal_actions` takes an **`Observation`**, not a `GameState`, so an agent enumerates its
  own moves without ever being handed the opponent's half of the board.
- An illegal action **returns** `legal=False` instead of raising. A learning policy emits
  invalid actions constantly; an environment that throws is unusable.
- State is frozen and the engine holds no module-level mutable state, no I/O, no clock and
  no RNG — its whole import list is five standard-library modules. One process can hold
  thousands of games with no locking and no defensive copying.
- Turn order arrives from outside, so self-play or a curriculum schedule needs no change here.

## Layout


```
src/hanoi_crossing/
  engine/         the game itself: model, rules, match driver
    model.py      frozen value types -- poles, actions, state, observation
    rules.py      legal_actions, step, the win condition
    match.py      runs a turn order against a policy
  transcript.py   the JSON format, and the only untrusted input
  cli/            replay and random-play frontends
examples/         a transcript of the brief's worked example
tests/            127 tests, including property tests over random play
```

## Development

| Task | Command |
| --- | --- |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy` |
| Test | `uv run pytest` |
| Audit dependencies | see the note below |

Auditing reads the locked set rather than the live environment, because the project
itself is installed editable and has no PyPI release to check:

```bash
uv export --format requirements-txt --no-emit-project --all-groups --no-hashes \
  -q -o requirements-audit.txt
uv run pip-audit --strict -r requirements-audit.txt
```

All four must pass before a commit. `pre-commit` enforces the first three locally:

```bash
uv tool install pre-commit
pre-commit install
```

### Standards applied here

- `ruff` runs with security (`S`), annotation (`ANN`), bugbear and pylint rule sets enabled.
- `mypy` runs in `strict` mode over both `src` and `tests`.
- Test coverage is gated at 90%; the build fails below it.
- No source file exceeds 500 lines.

## Security

The one untrusted input is the transcript file. [SECURITY.md](SECURITY.md) sets out the
threat model, the bans that back it up (no `pickle`, no `eval`, no `subprocess`, no
network), and the supply chain controls — zero runtime dependencies, a committed lockfile,
SHA-pinned CI actions, `pip-audit` and `gitleaks`.

## Use of AI tools

The brief asks what I used and how. I used **Claude Code (Opus 5)** throughout — directed,
not accepted wholesale.

**How we worked.** I set the sequence and the standards first: tooling and CI before any
feature code, zero runtime dependencies, strict lint and type checking from the start
rather than a permissive config tightened later, a threat model written for this program
rather than a generic one, tests on the flows that matter, and small commits behind pull
requests. From there it was iteration — it drafted, I reviewed, pushed back on what I
disagreed with, and sent it round again. Several things here exist because a review turned
them up rather than because the first draft had them: untrusted names are quoted before
they reach stderr, the driver refuses a board that has already been won, and the claims
this README makes are asserted by tests rather than stated in prose.

**Who did what.** It wrote most of the code, the tests, and the first drafts of the prose.
I set the direction, had it explain the game to me from first principles before I accepted
any of its rule interpretations, and made it re-verify its work against the brief rather
than take its word for it. The [design decisions](#design-decisions) above are the part
worth arguing about, and I would defend or revise any of them.

## Licence

MIT — see [LICENSE](LICENSE).
