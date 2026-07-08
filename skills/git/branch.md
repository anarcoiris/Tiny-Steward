---
name: git_branch
type: skill
requires: [pwsh, bash]
provides: [branch-management]
tags: [git, branch, checkout, switch]
related: [git_clone, git_merge, git_rebase]
---

# Git Branch

Create, list, switch, and delete branches.

## Common Operations

```bash
# List branches
git branch          # local
git branch -a       # all (including remote)

# Create and switch
git checkout -b <new-branch>
# or (modern git):
git switch -c <new-branch>

# Switch to existing branch
git checkout <branch>
git switch <branch>

# Delete branch
git branch -d <branch>        # safe delete (merged only)
git branch -D <branch>        # force delete

# Push new branch to remote
git push -u origin <branch>
```

## Errors

### Branch already exists

```bash
git checkout -b <branch>  # fails if branch exists
git checkout <branch>     # switch to existing instead
```

### Uncommitted changes prevent switch

```
error: Your local changes to the following files would be overwritten
```

Fix: stash or commit first:

```bash
git stash
git checkout <branch>
git stash pop
```
