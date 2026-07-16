---
name: docker_build
type: skill
requires: [pwsh, bash]
provides: [image-creation, dockerfile]
tags: [docker, build, dockerfile, image, container]
related: [docker, docker_compose]
---

# Docker Build

Create Docker images from a Dockerfile.

## Basic Build

```bash
docker build -t <name>:<tag> .
docker build -t myapp:latest .
```

## Dockerfile Template

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
```

## Multi-stage Build (smaller images)

```dockerfile
# Build stage
FROM node:20 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

## Errors

### COPY failed: file not found

Check `.dockerignore` — it may be excluding the file.

### pip install fails (network)

```dockerfile
RUN pip install --no-cache-dir --timeout 120 -r requirements.txt
```

## Tips

- Use `.dockerignore` to exclude `node_modules`, `.git`, `__pycache__`
- Order COPY statements: dependencies first, source last (better cache)
- Use `--no-cache-dir` with pip to reduce image size
