---
name: github_auth
type: skill
requires: [pwsh, bash]
provides: [github-authentication, token-auth]
tags: [github, authentication, token, pat, credential]
related: [git_clone, ssh_keys]
---

# GitHub Authentication

Configure authentication for GitHub repositories.

## HTTPS with Personal Access Token (PAT)

1. Generate token: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Clone with token:

```bash
git clone https://<TOKEN>@github.com/user/repo.git
```

3. Or configure credential storage:

```bash
git config --global credential.helper store
git clone https://github.com/user/repo.git
# Enter username and token when prompted (saved for future use)
```

On Windows (uses Credential Manager):

```powershell
git config --global credential.helper manager
```

## GitHub CLI (gh)

```bash
# Install (if not present)
winget install GitHub.cli

# Login
gh auth login

# Clone with gh
gh repo clone user/repo
```

## Errors

### Authentication failed

```
remote: Support for password authentication was removed
```

GitHub no longer accepts passwords. Use a PAT or SSH key instead.

### Token expired

Regenerate at GitHub → Settings → Developer settings → Personal access tokens.

### 403 Forbidden

- Token may lack required scopes
- Fine-grained token must have access to the specific repository
