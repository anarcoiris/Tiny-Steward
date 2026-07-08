---
name: http
type: skill
requires: []
provides: [http-request, api-call]
tags: [http, api, request, web, rest]
related: [python]
---

# HTTP Request

Make HTTP requests to APIs and web services.

## Usage

```xml
<action name="http" method="GET" url="https://api.github.com/repos/octocat/Hello-World"></action>
<action name="http" method="POST" url="http://localhost:8080/api/data">{"key": "value"}</action>
```

## Attributes

- `method`: GET, POST, PUT, DELETE, PATCH, HEAD
- `url`: target URL
- Body (between tags): sent as JSON if parseable, raw text otherwise

## Notes

- Response body capped at 8000 characters
- 30 second timeout
- For complex requests (headers, auth), use `python` with `httpx` or `requests`
