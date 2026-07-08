---
name: permission_denied
type: skill
requires: [pwsh, bash]
provides: [error-recovery]
tags: [permission, denied, access, error, sudo, chmod, acl, ownership]
related: [permissions, ssh_keys, find]
---

# Troubleshooting: Permission Denied

Diagnostic tree for "Permission denied" errors across platforms.

## Decision Tree

### SSH / Git

```
Permission denied (publickey)
→ ssh_keys skill
→ github_auth skill
```

### File System (Linux/WSL)

```
Permission denied: /path/to/file
│
├─ Check ownership: ls -la /path/to/file
│   └─ Wrong owner? → sudo chown $USER:$USER file
│
├─ Check permissions: stat file
│   └─ Too restrictive? → chmod 644 file  (or 755 for dirs/scripts)
│
└─ Need elevation? → sudo <command>
```

### File System (Windows)

```
Access to the path '...' is denied
│
├─ Check if file is locked: 
│   Get-Process | Where-Object { $_.Modules.FileName -eq "path" }
│
├─ Check ACL:
│   Get-Acl .\file | Format-List
│
├─ Run as Administrator:
│   Start-Process pwsh -Verb RunAs
│
└─ Take ownership:
    takeown /F file
    icacls file /grant "%USERNAME%:F"
```

### Docker

```
Permission denied inside container
│
├─ Wrong user in Dockerfile? → USER root / USER appuser
├─ Volume mount permissions? → check host dir permissions
└─ AppArmor/SELinux? → docker run --security-opt label:disable
```

### Python pip

```
Permission denied: /usr/lib/python...
→ Use virtual environment (venv skill)
→ Or: pip install --user <package>
```

## Common Patterns

| Error Context | Most Likely Fix |
|--------------|-----------------|
| `git clone/push` | SSH key not configured |
| Script execution | `chmod +x` or `Set-ExecutionPolicy` |
| Port < 1024 | Need sudo/admin |
| `/etc/` files | Need sudo |
| pip install | Use venv |
| Docker volume | Match UID/GID |
