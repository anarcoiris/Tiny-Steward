---
name: port_in_use
type: skill
requires: [pwsh, bash]
provides: [error-recovery, port-management]
tags: [port, in-use, bind, address, EADDRINUSE, already-allocated, listen, network]
related: [docker, systemd]
---

# Troubleshooting: Port Already in Use

Diagnostic tree for port binding errors.

## Symptoms

- `EADDRINUSE: address already in use`
- `Bind for 0.0.0.0:8080 failed: port is already allocated`
- `OSError: [Errno 98] Address already in use`
- `Only one usage of each socket address is normally permitted`

## Find What's Using the Port

### Windows / PowerShell

```powershell
# Find process on port
Get-NetTCPConnection -LocalPort 8080 | Select-Object OwningProcess, State
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess

# Or use netstat
netstat -ano | findstr :8080
```

### Linux / WSL

```bash
# Find process on port
lsof -i :8080
# or
ss -tulnp | grep :8080
```

## Fix

### Kill the process

```powershell
# Windows
Stop-Process -Id <PID> -Force

# Linux
kill <PID>
# or force:
kill -9 <PID>
```

### Use a different port

Change the application's port configuration. Most apps accept a `--port` flag or `PORT` environment variable.

### Docker-specific

```bash
# Find conflicting container
docker ps --filter "publish=8080"

# Stop it
docker stop <container>
```

## Prevention

- Use environment variables for ports: `$env:PORT` or `PORT=8080`
- Check port availability before starting: `Test-NetConnection -ComputerName localhost -Port 8080`
