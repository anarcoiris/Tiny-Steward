---
name: docker
type: hub
requires: [pwsh, bash]
provides: [containers, images, orchestration]
tags: [docker, containers, devops, deployment]
children: [docker_compose, docker_logs, docker_build]
related: []
---

# Docker

Container management and orchestration.

## Available Sub-Skills

| Need | Skill | Query |
|------|-------|-------|
| Multi-container apps | docker_compose | `help("docker compose")` |
| Debug container issues | docker_logs | `help("docker logs troubleshoot")` |
| Create images | docker_build | `help("docker build image")` |

## Quick Reference

```bash
# List containers
docker ps              # running
docker ps -a           # all

# Run a container
docker run -d --name <name> -p 8080:80 <image>

# Stop / remove
docker stop <container>
docker rm <container>

# Images
docker images
docker pull <image>
docker rmi <image>

# System cleanup
docker system prune -a
```

## Common Errors

### Docker daemon not running

```
Cannot connect to the Docker daemon
```

Start Docker Desktop or the Docker service.

### Port already in use

```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

→ See: **port_in_use** troubleshooting skill.
