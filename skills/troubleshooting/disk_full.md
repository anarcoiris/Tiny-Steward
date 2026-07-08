---
name: disk_full
type: skill
requires: [pwsh, bash]
provides: [error-recovery, disk-management]
tags: [disk, full, space, storage, no-space-left, cleanup, ENOSPC]
related: [docker, find]
---

# Troubleshooting: Disk Full / No Space Left

Diagnostic tree for disk space errors.

## Symptoms

- `ENOSPC: no space left on device`
- `There is not enough space on the disk`
- `Write failed: No space left on device`
- Build failures, database crashes, log rotation failures

## Diagnose

### Windows

```powershell
# Disk usage overview
Get-PSDrive -PSProvider FileSystem | Format-Table Name, @{N="Used(GB)";E={[math]::Round($_.Used/1GB,1)}}, @{N="Free(GB)";E={[math]::Round($_.Free/1GB,1)}}

# Largest files
Get-ChildItem -Recurse -File | Sort-Object Length -Descending | Select-Object -First 20 FullName, @{N="MB";E={[math]::Round($_.Length/1MB,1)}}

# Folder sizes
Get-ChildItem -Directory | ForEach-Object { $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [PSCustomObject]@{Name=$_.Name; MB=[math]::Round($size/1MB,1)} } | Sort-Object MB -Descending
```

### Linux / WSL

```bash
# Disk usage overview
df -h

# Largest directories
du -sh /* 2>/dev/null | sort -rh | head -20

# Largest files
find / -type f -size +100M 2>/dev/null | head -20
```

## Common Cleanups

### Docker (often the biggest offender)

```bash
docker system prune -a --volumes
# WARNING: removes all stopped containers, unused images, and volumes
```

### Windows temp files

```powershell
# Windows temp
Remove-Item $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue

# Windows Update cleanup
Dism.exe /online /Cleanup-Image /StartComponentCleanup
```

### Package caches

```bash
# pip cache
pip cache purge

# npm cache
npm cache clean --force

# conda
conda clean --all
```

### Log files

```bash
# Find large log files
find /var/log -type f -size +100M
# Truncate (keep file, clear content)
truncate -s 0 /var/log/large.log
```
