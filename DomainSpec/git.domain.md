---
id: git
type: domain
version: 1.0.0
purpose: Version control for tracking code changes over time.
extends: []

concepts:
  - id: repository
    name: Repository
  - id: commit
    name: Commit
  - id: tree
    name: Tree
  - id: blob
    name: Blob
  - id: branch
    name: Branch

tools:
  - id: git_status
    preference_rank: 1
  - id: git_diff
    preference_rank: 2
  - id: git_commit
    preference_rank: 3
  - id: bash
    preference_rank: 9
    precondition: No dedicated git tool covers this action

rules:
  - id: no_force_push
    statement: Never force-push to a shared branch without explicit confirmation.
    severity: hard
  - id: no_history_rewrite
    statement: Never rewrite public history.
    severity: hard
  - id: no_delete_without_confirm
    statement: Never delete branches without confirmation.
    severity: hard
  - id: prefer_atomic_commits
    statement: Prefer small, atomic commits over large batched ones.
    severity: soft

heuristics:
  - id: check_history_before_blame
    statement: Search commit history before blaming a file line-by-line.
    weight: 1
  - id: clean_tree_before_merge
    statement: Confirm a clean working tree before starting a merge.
    weight: 2

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
        - Working tree is clean
        - Commit message exists

  - id: pre_push_check
    when:
      stage: pre_action
      event: git_push
    priority: 5
    scope: git
    apply:
      rule_refs: [no_force_push, no_history_rewrite]

  - id: post_merge_verify
    when:
      stage: post_action
      event: git_merge
    priority: 10
    scope: git
    apply:
      procedure_ref: run_tests_after_merge

  - id: on_merge_conflict
    when:
      stage: on_error
      event: git_merge
    priority: 1
    scope: git
    apply:
      procedure_ref: investigate_merge_conflict

procedures:
  - id: create_branch
    kind: linear
    title: Create a new branch
    steps:
      - Check out the target branch
      - Verify current state is clean
      - Create the new branch with a descriptive name

  - id: squash_commits
    kind: linear
    title: Squash commits before merging
    steps:
      - Identify the commits to squash
      - Generate a meaningful combined commit message
      - Apply the squash and push

  - id: run_tests_after_merge
    kind: linear
    title: Run tests and verify integration
    steps:
      - Run the full test suite
      - Confirm the merged branch builds cleanly

  - id: recover_lost_commit
    kind: conditional
    title: Recover a commit that seems to be gone
    entry: q_was_committed
    steps:
      - id: q_was_committed
        action: Was the change ever committed?
        branches:
          "yes": step_checkout
          "no": step_reflog
      - id: step_checkout
        action: git checkout <previous-commit>
      - id: step_reflog
        action: Use `git reflog` to locate and recover the dangling commit

  - id: investigate_merge_conflict
    kind: entrypoint
    title: Investigate and resolve a merge conflict
    entry: q_conflict_files
    steps:
      - id: q_conflict_files
        action: Check which files are in conflict
        branches:
          "resolvable": step_review_history
          "unclear": step_abort
      - id: step_review_history
        action: Review commit history for both branches
        next: step_propose
      - id: step_abort
        action: Run `git merge --abort` to back out safely
        next: step_propose
      - id: step_propose
        action: Propose a resolution strategy to the user

memory_refs:
  - git.repo.trunk_based_workflow
  - git.repo.semver_commits

policies_imported:
  - security
---

# Git

## Purpose

Version control for tracking code changes over time.

## Notes for humans reading this file

This body exists for readability; the YAML front matter above is the
source of truth a parser validates against `domainspec.schema.json`.
If the two ever disagree, the front matter wins.

- `pre_push_check` (priority 5) runs before `pre_commit_check` (priority 10)
  when both apply to the same action — lower priority number runs first.
- `on_merge_conflict` fires the `investigate_merge_conflict` entrypoint
  automatically on `git_merge` failure; a user can also invoke it by name
  at any time, since it's `kind: entrypoint`, not just called internally.
- `security` is imported as a policy rather than duplicated here — see
  `policies/security.md`. Because personas typically pin imported policies
  (§10 of the spec), it stays loaded even under context pressure.

## Examples

**Good**
```bash
git status
git add .
git commit -m "Fix login issue"
```

**Bad** — violates `no_force_push` (hard rule, blocks the action)
```bash
git push -f origin main
```
