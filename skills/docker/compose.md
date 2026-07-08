---
name: docker_compose
type: skill
requires: [pwsh, bash]
provides: [multi-container-orchestration]
tags: [docker, compose, multi-container, yaml, orchestration, services]
related: [docker, docker_logs, docker_build]
---

# Docker Compose

Define and run multi-container applications with `docker-compose.yml`.

## Common Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a specific service
docker compose restart <service>

# View logs
docker compose logs -f [service]

# Rebuild and start
docker compose up -d --build

# Scale a service
docker compose up -d --scale <service>=3
```

## Compose File Structure

```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./html:/usr/share/nginx/html
    depends_on:
      - api
  api:
    build: ./api
    environment:
      DATABASE_URL: postgres://db:5432/app
    depends_on:
      - db
  db:
    image: postgres:16
    volumes:
      - db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: secret

volumes:
  db-data:
```

## Errors

### Container exits immediately

1. `docker compose ps` — check exit code
2. `docker compose logs <service>` — check error messages
3. Common causes: missing env vars, wrong command, port conflicts

### Network issues between services

Services communicate by service name (not localhost):

```
# From "web" container, reach "api":
http://api:8080
```
