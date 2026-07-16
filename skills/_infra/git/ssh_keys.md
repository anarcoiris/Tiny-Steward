---
name: ssh_keys
type: skill
requires: [pwsh, bash]
provides: [ssh-authentication, key-management]
tags: [ssh, keys, authentication, ed25519, publickey, permission-denied]
related: [git_clone, github_auth]
---

# SSH Keys

Generate, configure, and troubleshoot SSH keys for authentication.

## Generate a new SSH key (Ed25519, recommended)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Default location: `~/.ssh/id_ed25519` (private) and `~/.ssh/id_ed25519.pub` (public).

On Windows PowerShell:

```powershell
ssh-keygen -t ed25519 -C "your_email@example.com"
# Keys saved to: C:\Users\<username>\.ssh\id_ed25519
```

## Add key to SSH agent

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

On Windows:

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic
Start-Service ssh-agent
ssh-add $env:USERPROFILE\.ssh\id_ed25519
```

## Copy public key

```bash
cat ~/.ssh/id_ed25519.pub
```

On Windows:

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | Set-Clipboard
```

Then add to GitHub/GitLab/etc. settings → SSH Keys.

## Test SSH connection

```bash
ssh -T git@github.com
```

Expected: `Hi <username>! You've successfully authenticated`

## Errors

### Permission denied (publickey)

1. Check key exists: `ls ~/.ssh/id_ed25519*`
2. Check agent has key: `ssh-add -l`
3. If empty, add: `ssh-add ~/.ssh/id_ed25519`
4. Verify public key is on GitHub: Settings → SSH Keys

### Too many authentication failures

```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 git@github.com
```

### Key permissions too open (Linux/WSL)

```bash
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
chmod 700 ~/.ssh
```
