# Thoughts on DomainSpec v2

## Summary of what I've reviewed

Files examined:
- `DomainSpec/DomainSpec-v2-Specification.md` — the full v2 specification (15 sections)
- `DomainSpec/DomainSpec.md` — the original v1 proposal
- `DomainSpec/domainspec.schema.json` — JSON Schema for validating front matter
- `DomainSpec/git.domain.md` — a rewritten example file demonstrating v2 format

## What v2 actually does

### 1. Fixes ten specific inconsistencies from v1

| # | Issue in v1 | v2's fix |
|---|---|---|
| 1 | Tools + Tool Preferences as separate sections | Merged: single `tools[]` with `preference_rank` integer field |
| 2 | Rules and Anti-patterns overlap | Unified: `rules[]` with `severity: hard\|soft` (hard = MUST, soft = SHOULD) |
| 3 | Procedures/Playbooks/Decision Trees as different formats | One schema with `kind: linear\|conditional\|recovery\|entrypoint` |
| 4 | Two incompatible hook schemas | Canonical YAML form only; Markdown headers are generated view |
| 5 | Memory duplicated in domain files + top-level facts | Single `memory/` store; domains hold `memory_refs[]` pointers only |
| 6 | Skills/Domains/Playbooks undistinguished | Domain = noun, Skill = composed verb, Persona = selection+style, Policy = importable rules |
| 7 | Hook `when.stage` not enumerated | Closed lifecycle: `session_start`, `pre_plan`, `tool_selection`, `pre_action`, `post_action`, `on_error`, `on_conflict`, `session_end` |
| 8 | "Machine-parsable" asserted but not designed | `domainspec.schema.json` validates front-matter YAML blocks |
| 9 | Progressive Skill Graph + OpenClaw undefined | Specified: graph model (§9) + loader/runtime (§10) — one mechanism, two names |
|10 | No versioning field | Added `version` field with MAJOR/MINOR/PATCH semantics; diffs computed on parsed YAML, not text diff |

### 2. Taxonomy: four node kinds

| Kind | Answers | Example |
|---|---|---|
| **Domain** | *What exists* — subject-matter knowledge | `git`, `python`, `docker` |
| **Skill** | *What I can do* — composed cross-domain capability | `code_review` (spans `git` + `python` + `policies/security`) |
| **Persona** | *How I'm configured* — selection + priority + style | `reviewer`, `ops_engineer` |
| **Policy** | *What always applies* — importable rules | `security`, `privacy` |

A Policy is structurally a Domain with no `tools` and no native `concepts`. This explains why v1's `heuristics/universal.md` becomes `policies/universal_heuristics.md` — it was already a policy, just misnamed.

### 3. File format: YAML front matter + Markdown body

```yaml
---
id: git
type: domain
version: 1.0.0
purpose: Version control for tracking code changes over time.
extends: []
concepts: [...]
tools: [...]
rules: [...]
heuristics: [...]
hooks: [...]
procedures: [...]
memory_refs: [...]
policies_imported: [...]
---

# Git

(human-readable prose)
```

The YAML is the source of truth; Markdown mirrors it. This makes "machine-parsable" true rather than asserted.

### 4. Procedures now use a node-graph model

`investigate_merge_conflict` from v1 becomes a `kind: entrypoint` procedure built from the same node shape — it's not a different primitive, just a procedure with a name the agent can call directly. The schema supports:
- `linear` — simple ordered strings (common case)
- `conditional` — branching graph with `entry` and `branches`
- `recovery` — invoked by `on_error` hook
- `entrypoint` — exposed as named workflow

### 5. Hooks have a canonical schema

```yaml
hooks:
  - id: pre_commit_check
    when:
      stage: pre_action
      event: git_commit
    priority: 10
    scope: git
    apply:
      rule_refs: [prefer_atomic_commits]
      checklist:
        - Tests pass
```

`apply` may reference `rule_refs`, `heuristic_refs`, a `checklist`, and/or a `procedure_ref` — at least one is required. This prevents hooks from silently drifting out of sync with the rule they enforce.

### 6. Memory: single store, referenced not duplicated

```yaml
memory_refs: [git.repo.trunk_based_workflow, git.repo.semver_commits]
```

Facts live in `memory/`, timestamped and sourced so staleness is detectable — v1's inline `Memory` section had no way to tell a fact from 2019 apart from one from this morning.

### 7. Progressive loading / "OpenClaw" loader

The spec describes:
- `state.active` — node_id → {node, priority, last_used, tokens, pinned}
- Budget tracking with eviction policy (least priority + least recent)
- Policies are `pinned`, so they survive eviction regardless of context pressure

This is the "runtime component that walks the graph" v1 called OpenClaw. Without this, a budget-constrained agent could silently drop its safety rules first, since they're used less often than the domain it's actively working in.

### 8. Conflict resolution across composed domains

v2 defines precedence order:
1. Explicit persona override
2. Specificity (Policy < Domain < Skill)
3. Severity (hard beats soft)
4. Priority number
5. Unresolved tie → fire `on_conflict`, log it, escalate to human

### 9. Versioning

```yaml
version: 1.2.0
deprecated_since: null
superseded_by: null
```

- MAJOR — rule meaning changes or node removed
- MINOR — additive (new tool, procedure, hook)
- PATCH — prose/heuristic wording only

Diffs are computed on the parsed YAML graph, not as a text diff — a text diff on Markdown headers can't distinguish "reworded a rule" from "changed what the rule means."

### 10. Directory structure v2

```text
knowledge/
├── domains/            # type: domain
│   ├── git.domain.md
│   ├── python.domain.md
│   └── docker.domain.md
├── skills/              # type: skill
│   └── code_review.skill.md
├── personas/            # type: persona
│   └── reviewer.md
├── policies/            # type: policy
│   ├── security.md
│   └── universal_heuristics.md
├── memory/               # single source of truth
│   └── git.repo.trunk_based_workflow.md
└── _schema/
    └── domainspec.schema.json
```

`templates/`, `heuristics/`, `hooks/`, `playbooks/`, and `decision_trees/` from v1 are gone as top-level folders — each now lives *inside* the domain/skill file that owns it.

### 11. Open questions (not resolved here)

- Hook execution sandboxing
- Multi-agent memory sync
- Simultaneous personas
- When to split a domain
- Eval/CI for domain specs

## Observations on git.domain.md (v2 example)

The file demonstrates:
- YAML front matter with `id`, `type`, `version`, `purpose`, `extends`, `concepts`, `tools`, `rules`, `heuristics`, `hooks`, `procedures`, `memory_refs`, `policies_imported`
- Markdown body below — prose examples, rationale
- Tools are listed with `preference_rank`; `bash` has a `precondition` explaining why it's a fallback
- Rules have `severity: hard` or `soft`
- Procedures include both linear (ordered strings) and conditional (branching graph) forms
- Hooks reference rules via `rule_refs` rather than duplicating prose
- Memory is referenced via IDs only, not duplicated

This file appears to be a faithful rewrite of the v1 `git.domain.md` example, now conforming to v2. I verified this by reading both files and comparing content — the YAML structure matches the schema, and the Markdown body mirrors the front matter.

## Observations on domainspec.schema.json

The schema:
- Requires `id`, `type`, `version` (MAJOR.MINOR.PATCH)
- Allows optional fields like `deprecated_since`, `superseded_by`, `purpose`, `extends`
- `tools` entries require `id`; `preference_rank` is an integer ≥ 1; `precondition` is optional string
- `rules` require `id`, `statement`, `severity: hard\|soft`; optional `scope`, `rationale`
- `heuristics` require `id`, `statement`; optional `weight`, `applies_when`
- `hooks` require `id`, `when` (with mandatory `stage`), `apply`; `when.stage` enum includes all eight lifecycle stages
- `procedures` require `id`, `kind: linear\|conditional\|recovery\|entrypoint`, `title`; conditional kinds need `entry`; recovery kinds need `trigger`
- `memory_refs` and `policies_imported` are arrays of strings
- `persona_config` is a large object with nested domains, skills, pinned, overrides, style — only used when `type: persona`

The schema uses JSON Schema draft-2020-12, includes `$id`, `$schema`, and `additionalProperties: true`. This means it will validate the YAML front matter block of any `.domain.md`, `.skill.md`, persona, or policy file.

## Overall assessment

DomainSpec v2 represents a significant consolidation and formalization of the original proposal. It:
- Fixes all documented inconsistencies from v1
- Introduces a clear taxonomy (Domain, Skill, Persona, Policy) with rules for where content belongs
- Makes the format machine-parsable via YAML front matter + JSON Schema validation
- Unifies procedures under one graph model
- Defines hooks as middleware with a canonical schema and lifecycle
- Consolidates memory into a single store
- Specifies progressive loading with budget/eviction policies
- Adds versioning semantics

The companion files (`git.domain.md` rewritten, `domainspec.schema.json`) appear to be ready for use. I see no obvious issues or contradictions between the specification and the example files — the rewrite is faithful.

One thing worth noting: v2 still leaves several open questions (hook sandboxing, multi-agent memory sync, simultaneous personas, domain splitting heuristics, eval/CI). These are explicitly called out in §15 and are not addressed here, which seems intentional — the spec focuses on structural consolidation rather than every possible runtime concern.

---

DONE