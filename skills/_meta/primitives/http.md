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
<tool_call>
<function=http>
<parameter=method>
GET
</parameter>
<parameter=url>
https://httpbin.org/get
</parameter>
</function>
</tool_call>
```
