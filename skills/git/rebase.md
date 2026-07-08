---
name: git_rebase
type: skill
requires: [pwsh, bash]
provides: [branch-rebase, history-cleanup]
tags: [git, rebase, history, squash]
related: [git_branch, git_merge]
---

# Git Rebase

Replay commits from one branch onto another, creating a linear history.

## Interactive Rebase (squash/edit commits)

```bash
git rebase -i HEAD~<N>      # last N commits
git rebase -i <base-branch>  # rebase onto branch
```

In the editor, change `pick` to:
- `squash` (s) — combine with previous commit
- `reword` (r) — change commit message
- `edit` (e) — stop to amend
- `drop` (d) — remove commit

## Rebase onto main

```bash
git checkout feature
git rebase main
```

## Errors

### Rebase conflicts

```bash
# After resolving conflicts:
git add <files>
git rebase --continue

# To abort:
git rebase --abort
```

### Cannot rebase: uncommitted changes

```bash
git stash
git rebase main
git stash pop
```

## Warning

- Never rebase commits that have been pushed and shared with others
- Rebase rewrites history — force push required: `git push --force-with-lease`
