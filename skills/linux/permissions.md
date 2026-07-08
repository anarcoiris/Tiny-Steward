---
name: permissions
type: skill
requires: [pwsh, bash]
provides: [file-permissions, access-control]
tags: [permissions, chmod, acl, access, denied, ownership]
related: [find, permission_denied]
---

# File Permissions

Manage file and directory permissions on Linux and Windows.

## Linux / WSL (chmod)

```bash
# Read/write/execute for owner, read/execute for group/others
chmod 755 script.sh

# Read/write for owner only
chmod 600 private_key

# Recursive
chmod -R 755 directory/

# Change ownership
chown user:group file
chown -R user:group directory/
```

### Permission Numbers

| Number | Permission |
|--------|-----------|
| 7 | rwx (read + write + execute) |
| 6 | rw- (read + write) |
| 5 | r-x (read + execute) |
| 4 | r-- (read only) |
| 0 | --- (no permission) |

## Windows (ACL)

```powershell
# View permissions
Get-Acl .\file.txt | Format-List

# Grant full control
$acl = Get-Acl .\file.txt
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Username","FullControl","Allow")
$acl.SetAccessRule($rule)
Set-Acl .\file.txt $acl

# Take ownership (admin)
takeown /F file.txt
icacls file.txt /grant "%USERNAME%:F"
```

## Errors

### Permission denied

→ See troubleshooting skill: **permission_denied**
