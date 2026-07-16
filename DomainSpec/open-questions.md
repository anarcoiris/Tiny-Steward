# Open Questions in DomainSpec v2

*Documenting deliberate gaps — not omissions.*

---

## 1. Hook execution sandboxing

**What’s missing:** A hook can trigger tool calls; nothing defines what permissions a hook inherits versus the agent that loaded it.

### Why it matters

- A hook runs *inside* the domain’s context, but may call tools that are scoped differently (e.g., `bash` vs `git_status`).
- If a hook can arbitrarily invoke any tool, it could bypass security rules enforced by policies.
- Conversely, overly restrictive sandboxing could prevent legitimate workflows (e.g., a pre-commit hook needing to run tests).

### Proposed approaches

#### Option A: Hook inherits parent agent’s permission set

- Hooks are executed with the same capability mask as the agent that loaded the domain.
- Pros: Simple; no extra metadata needed.
- Cons: Doesn’t allow fine-grained control (e.g., a hook should only be able to call tools from its own domain).

#### Option B: Hooks declare their required tools

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
      required_tools: [git_status, bash]  # explicit list
```

- Pros: Clear contract; static analysis can verify the hook only uses allowed tools.
- Cons: Requires schema update; may be overkill for simple hooks.

#### Option C: Hooks run in a restricted subprocess

- All hooks execute via `pwsh` or `bash` with a limited environment and no direct tool calls; they must invoke tools through explicit procedure references.
- Pros: Strong isolation.
- Cons: Adds latency; may break existing workflows that rely on direct tool access.

**Recommendation:** Start with **Option B** (declare required tools) as the default, with an optional `sandbox_mode` flag that, when set, forces execution via a restricted subprocess. This balances simplicity and security.

---

## 2. Multi-agent memory sync

**What’s missing:** `memory/` assumes one writer. Concurrent agents updating the same `MemoryFact` needs a merge policy.

### Why it matters

- In multi-agent setups (e.g., supervisor + worker), both may observe facts about the repo and write to `memory/`.
- Without coordination, updates could overwrite each other, losing information or creating contradictory facts.

### Proposed approaches

#### Option A: Write-only-per-fact with versioning

- Each `MemoryFact` includes a `version` field; concurrent writes increment it atomically (via file locking or DB).
- Conflicts are detected by comparing versions before read.
- Pros: Simple, preserves all updates.
- Cons: Requires a backend that supports atomic versioning.

#### Option B: Merge policy per fact

```yaml
# memory/git.repo.workflows.md
---
id: git.repo.workflows
subject: this repository
fact: Uses a trunk-based workflow.
confidence: high
source: observed
last_updated: 2026-06-01
merge_policy:
  mode: optimistic
  conflict_resolution: keep_higher_confidence
---
```

- `mode`: `optimistic` (try to merge, fallback to user), `pessimistic` (require lock), `lock` (exclusive).
- `conflict_resolution`: `keep_higher_confidence`, `keep_newest`, `user_review`.
- Pros: Explicit, flexible.
- Cons: Adds complexity; requires runtime handling.

#### Option C: Centralized memory store

- Replace `memory/` with a database-backed store (SQLite or similar).
- Transactions handle concurrency; schema ensures uniqueness of `id`.
- Pros: Robust, scalable.
- Cons: Deviates from the file-based design; may not suit all environments.

**Recommendation:** Adopt **Option B** with an `merge_policy` field in each `MemoryFact`. Default to `optimistic` with `keep_higher_confidence`. Provide a simple CLI tool (`mcp-memory-sync`) that implements the merge logic.

---

## 3. Simultaneous personas

**What’s missing:** §11 resolves conflicts *within* one persona’s active graph; two personas active at once (e.g., a supervisor and a sub-agent) isn’t addressed.

### Why it matters

- A supervisor persona may import `security` policy; a worker persona may not.
- Rules or heuristics could conflict (e.g., supervisor says “no shell commands,” worker needs `bash`).
- Need to decide precedence without breaking either persona’s intent.

### Proposed approaches

#### Option A: Persona isolation with explicit cross-persona rules

- Each persona maintains its own active graph; conflicts only arise if a rule is explicitly shared (via `shared_rules` list).
- Pros: Clean separation; no hidden interactions.
- Cons: Requires schema extension and runtime tracking of shared rules.

#### Option B: Global conflict resolution layer

- When two personas load simultaneously, a global resolver runs after both graphs are assembled, applying the same precedence order as §11 but across personas.
- Pros: Unified treatment.
- Cons: Complex; may require a separate “conflict” node type.

#### Option C: Persona merge into a composite

- Before activation, two personas are merged into a temporary composite persona that has both domain selections and combined overrides.
- Pros: Simple; can be done at load time.
- Cons: May lose nuance (e.g., one persona’s style could be overridden by the other).

**Recommendation:** Start with **Option A** — extend the `persona_config` schema to include a `shared_rules` list and a `cross_persona_resolution` field. Default resolution is “fail open” (log conflict, allow both rules to stand) unless explicitly set to “merge.” This keeps personas isolated by default but allows controlled interaction when needed.

---

## 4. When to split a domain

**What’s missing:** No size/complexity heuristic for “this domain file is too big, split it.”

### Why it matters

- Large domain files (e.g., `git.domain.md` with many tools, rules, procedures) become hard to edit and may exceed context budgets.
- Need guidance on when a split is warranted.

### Proposed approaches

#### Option A: Token-count threshold

- Split when `estimate_tokens(node)` exceeds a configurable limit (e.g., 80% of MAX_CONTEXT_TOKENS).
- Pros: Simple, budget-aware.
- Cons: May split prematurely for dense content.

#### Option B: Rule/procedure count threshold

- Split if the file contains more than N rules or procedures (e.g., 50).
- Pros: Directly addresses editability.
- Cons: Doesn’t account for token cost.

#### Option C: User-initiated split request

- Provide a CLI command (`tiny-steward split-domain <id>`) that prompts the user to choose split points.
- Pros: Human-in-the-loop, respects intent.
- Cons: Not automatic.

**Recommendation:** Combine **Option A** and **Option B**: auto-split when token count > 75% of budget *or* rule/procedure count > 40. Offer a CLI tool to inspect and manually split, logging the split decision with rationale. This respects both budget and editability concerns.

---

## 5. Eval/CI for domain specs

**What’s missing:** Nothing defines how you’d regression-test a change to a rule or hook before merging it, the equivalent of a test suite for knowledge.

### Why it matters

- Changing a rule (e.g., making `no_force_push` from soft to hard) could break existing workflows.
- Need automated checks: static analysis, runtime simulation, and integration tests.

### Proposed approaches

#### Option A: Static test annotations in the spec

```yaml
# inside git.domain.md
tests:
  - id: no_force_push_static
    kind: static
    description: Verify rule is marked hard
```

- Pros: Simple; can be parsed by CI.
- Cons: Limited to superficial checks.

#### Option B: Runtime simulation harness

- A Python script that loads a domain, runs all hooks with mock tool calls, and asserts expected outcomes.
- Pros: Comprehensive; catches behavioral regressions.
- Cons: Requires maintaining test infrastructure.

#### Option C: Integration tests via `tiny-steward` CLI

- Use the existing `mcp` primitives to run actual tool calls against a test repo, asserting that rules are enforced.
- Pros: Real-world validation.
- Cons: Slower; needs a test environment.

**Recommendation:** Provide both **Option B** (simulation harness) and **Option C** (CLI integration tests). Include a `test/` subdirectory under each domain file with YAML annotations that map to simulation scripts. CI runs the harness first for speed, falls back to CLI integration if static checks pass but runtime behavior is uncertain.

---

## 6. Other potential gaps

- **Persona style enforcement** — currently just text; could be validated against a grammar.
- **Policy import order** — when multiple policies are imported, which takes precedence? (covered by §11, but worth explicit rule).
- **Graph traversal limits** — OpenClaw’s budget applies to token count; should we also limit node depth or edge count?

These can be addressed incrementally as the ecosystem grows.

---

DONE