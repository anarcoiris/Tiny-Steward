---
name: systemd
type: skill
requires: [bash]
provides: [service-management, daemon]
tags: [systemd, service, daemon, linux, systemctl, startup]
related: [permissions, find]
---

# Systemd — Service Management

Manage system services on Linux.

## Common Commands

```bash
# Start/stop/restart
sudo systemctl start <service>
sudo systemctl stop <service>
sudo systemctl restart <service>

# Status
systemctl status <service>

# Enable at boot
sudo systemctl enable <service>
sudo systemctl disable <service>

# List all services
systemctl list-units --type=service

# View logs
journalctl -u <service> --no-pager -n 50
journalctl -u <service> -f  # follow
```

## Create a Custom Service

```ini
# /etc/systemd/system/myapp.service
[Unit]
Description=My Application
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/myapp
ExecStart=/opt/myapp/run.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now myapp
```

## Errors

### Service failed to start

1. `systemctl status <service>` — check error message
2. `journalctl -u <service> -n 100` — check full logs
3. Common: wrong path, wrong user, missing dependency, port in use
