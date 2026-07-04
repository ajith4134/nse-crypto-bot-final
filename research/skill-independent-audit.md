# Skill ① — independent-audit: OSS reuse research (Phase 1 SELECT)

_Date: 2026-07-04 · target: report-only independent code+architecture connectivity evaluator for a Python + React trading codebase. Maps how all files/functions connect, finds orphan modules / unused functions / unwired dashboard endpoints / missing links, suggests better connections + function usage._

Reuse-first: these are proven, maintained tools. The skill ORCHESTRATES them into one honest connectivity audit — we write only the glue (target selection, dashboard route↔panel cross-check, report synthesis).

## Python — import & call graph, dead code, contracts

| Project | Repo | Key capability | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **grimp** | python-grimp/grimp | Programmatic `ImportGraph` API: children/descendants, direct & upstream imports, **shortest import chains**, import line numbers; Rust-backed (fast). | v3.14, active | ★★★★★ | **CORE** — the connectivity engine (who imports whom, orphans, chains). |
| **import-linter** | seddonym/import-linter | Architecture **contracts / fitness functions**: declare layers & allowed boundaries, fail when violated. Built on grimp (same author). | active | ★★★★★ | **CORE** — encodes "what SHOULD connect to what" → powers better-connection suggestions. |
| **vulture** | jendrikseipp/vulture | Dead code: unused classes/functions/vars + **unreachable code**, 60–100% confidence, `--sort-by-size`. AST-based. | active | ★★★★★ | **CORE** — the "unused functions / orphans" detector. |
| **pyan3** | Technologicat/pyan | Static **call graph** (who calls whom), Py3.10–3.14, call-path listing, cycle detection. | actively maintained | ★★★★☆ | **INCLUDE** — call-level wiring (deeper than imports). Better-maintained than code2flow for Python-only. |
| **pydeps** | thebjorn/pydeps | CLI import-graph **visualization**, bytecode-based, highlights **import cycles** (`--show-cycles`). Needs Graphviz. | active | ★★★☆☆ | **OPTIONAL (viz)** — pretty SVGs + cycle picture; grimp already gives cycles programmatically. |
| code2flow | scottrogowski/code2flow | Multi-lang call graphs (Py/JS/Ruby/PHP). | maintainer "spread thin" | ★★★☆☆ | SKIP for Python (pyan3 better); keep in mind for mixed-lang. |

## React / TypeScript dashboard

| Project | Repo | Key capability | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| **dependency-cruiser** | sverweij/dependency-cruiser | JS/TS dep graph + **rules** (which modules may/may not talk), **orphan detection**, circular-dep errors, navigable HTML report, CI. | active | ★★★★★ | **CORE (frontend)** — orphans + boundary rules mirror import-linter for the React side. |
| madge | pahen/madge | Simple JS/TS/ES6 dep graph + circular detection. | active | ★★★☆☆ | LIGHT ALT — quick circular check; dep-cruiser is richer. |
| skott | antoinecoulon/skott | "new madge", modern graph API. | active | ★★★☆☆ | Watch — alt to dep-cruiser if we want a JS API. |

## Recommendation — STITCH (complementary, not one winner)
**Python:** grimp (connectivity graph) + import-linter (should-connect contracts) + vulture (dead/unused) + pyan3 (call graph) [+ pydeps for optional viz].
**Frontend:** dependency-cruiser (orphans + boundary rules) [madge as light fallback].
**Glue we write:** (a) target the repo's real top-level packages; (b) cross-reference `INDEX.md`; (c) **dashboard honest-wiring check** — parse `dashboard/server.py` API routes vs `dashboard/web/src` fetch/api calls to flag endpoints defined-but-unused and UI calls with no backing route; (d) synthesize a single independent, fresh-eyes audit report with concrete better-connection + function-usage suggestions. No edits.

All pip/npm installable → ask-to-install; skill degrades gracefully to whatever is present and names what to install for full coverage.

Sources: grimp (github.com/python-grimp/grimp, pypi.org/project/grimp), import-linter (github.com/seddonym/import-linter), vulture (github.com/jendrikseipp/vulture), pyan3 (github.com/Technologicat/pyan), pydeps (github.com/thebjorn/pydeps), dependency-cruiser (github.com/sverweij/dependency-cruiser), madge (github.com/pahen/madge), skott (dev.to/antoinecoulon/introducing-skott-the-new-madge-1bfl).
