---
name: git_clone
type: skill
requires: [pwsh, bash]
provides: [repository, source-code]
tags: [git, clone, repository, source-control, checkout]
related: [git_branch, git_merge, ssh_keys, github_auth]
---

# Git Clone

Clone a remote repository to a local directory.

## When

- Repository doesn't exist locally
- First checkout of a project
- Creating a fresh working copy

## Steps

```bash
git clone <repo_url> [target_dir]
```

For shallow clone (faster, no full history):

```bash
git clone --depth 1 <repo_url>
```

For a specific branch:

```bash
git clone --branch <branch_name> <repo_url>
```

## Errors

### Permission denied (publickey)

SSH key not configured or not added to the remote. See: **ssh_keys**, **github_auth**.

```
git@github.com: Permission denied (publickey).
fatal: Could not read from remote repository.
```

Fix: use HTTPS instead, or configure SSH key:

```bash
git clone https://github.com/user/repo.git
```

### Repository not found

```
ERROR: Repository not found.
```

- Verify the URL is correct
- For private repos, ensure you have access
- Check if the repository was renamed or moved

### SSL certificate problem

```
fatal: unable to access '...': SSL certificate problem
```

Temporary fix (insecure):

```bash
git -c http.sslVerify=false clone <url>
```

## Notes

- HTTPS requires credentials (token or password) for private repos
- SSH requires key setup but avoids repeated auth prompts
- Use `--recurse-submodules` if the repo uses git submodules
