---
name: docker_logs
type: skill
requires: [pwsh, bash]
provides: [container-debugging, log-analysis]
tags: [docker, logs, debug, troubleshoot, container, exit]
related: [docker, docker_compose]
---

# Docker Logs & Troubleshooting

Diagnose container issues using logs and inspection.

## View Logs

```bash
# Follow logs in real time
docker logs -f <container>

# Last N lines
docker logs --tail 50 <container>

# With timestamps
docker logs -t <container>

# Compose service logs
docker compose logs -f <service>
```

## Container Won't Start / Exits Immediately

Diagnostic sequence:

1. **Check status**: `docker ps -a` — look at STATUS and EXIT CODE
2. **Read logs**: `docker logs <container>`
3. **Check exit code**:
   - `0` — normal exit (command completed)
   - `1` — application error
   - `137` — OOM killed (out of memory)
   - `139` — segfault
   - `143` — SIGTERM (graceful shutdown)
4. **Inspect**: `docker inspect <container> | grep -A 5 "State"`
5. **Verify mounts**: `docker inspect <container> | grep -A 10 "Mounts"`
6. **Verify ports**: `docker port <container>`

## Exec Into Running Container

```bash
docker exec -it <container> sh
# or for bash:
docker exec -it <container> bash
```

## Resource Issues

```bash
# Check resource usage
docker stats

# Check disk usage
docker system df
```
