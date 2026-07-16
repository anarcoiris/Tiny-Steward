---
name: git_merge
type: skill
requires: [pwsh, bash]
provides: [branch-integration]
tags: [git, merge, conflict, integration]
related: [git_branch, git_rebase]
---

# Git Merge

Integrate changes from one branch into another.

## Steps

```bash
# Switch to target branch
git checkout main

# Merge source branch
git merge <feature-branch>

# If conflicts, resolve then:
git add <resolved-files>
git merge --continue
```

## Errors

### Merge conflicts

```
CONFLICT (content): Merge conflict in <file>
Automatic merge failed; fix conflicts and then commit the result.
```

1. Open conflicted files — look for `<<<<<<<`, `=======`, `>>>>>>>`
2. Edit to resolve
3. `git add <file>` for each resolved file
4. `git merge --continue` or `git commit`

### Abort a merge

```bash
git merge --abort
```

## Tips

- Use `--no-ff` to always create a merge commit: `git merge --no-ff <branch>`
- Use `git log --oneline --graph` to visualize branch history
