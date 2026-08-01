---
name: astrophotography_agent
description: Autonomous Astrophotography Copilot for N.I.N.A. (Nighttime Imaging 'N' Astronomy) using local LLMs & custom remote Caddy/DDNS APIs.
type: skill
provides: [nina-agent, remote-astronomy-control, telescope-autopilot, star-inspection]
requires: []
tags: [nina, astronomy, telescope, camera, mount, caddy, ddns, qwythos, llama.cpp, astrophotography]
---

# Autonomous Astrophotography Agent (Tiny Steward + NINA)

An autonomous copilot skill that enables Tiny Steward to control N.I.N.A astrophotography rigs over local or remote Caddy/DDNS HTTPS APIs, executing target slewing, status reporting, image captures, focus monitoring, and target sequence orchestration.

## Features & Capabilities

- **Remote API Support**: Supports custom endpoints via Caddy reverse proxies & DDNS (e.g. `https://my-rig.ddns.net/v2/api`) or local IP (`http://127.0.0.1:1888/v2/api`).
- **Aggregated System Status**: Single tool invocation (`nina_get_system_status`) returns connected status for Camera, Mount, Focuser, FilterWheel, Guider, and Dome.
- **On-Premise LLM Integration**: Optimized for execution with Qwythos/llama.cpp (`:11440`/`:11439`) or Ollama profiles (`gemma-4-12b`).
- **Target Pointing & Guiding**: Slew to RA/DEC coordinates or catalog targets, start/stop guiding, and verify plate solving.
- **Image Quality & Focus Analysis**: Review HFR, star counts, ADU levels, and trigger autofocus when degradation is detected.

## Remote Caddy & DDNS Configuration

To point Tiny Steward at a remote N.I.N.A instance over Caddy HTTPS / DDNS:

```bash
# Set environment variable before starting Tiny Steward or MCP server
$env:NINA_BASE_URL="https://your-subdomain.ddns.net/v2/api"
```

Alternatively, pass `base_url` directly when initializing the `NinaAPIClient`.

## Usage Examples

### 0. Ensure N.I.N.A is Running & Advanced API is Ready
If N.I.N.A is not running on the host, the agent uses `nina_ensure_running` to locate `NINA.exe`, launch the process asynchronously, and poll until the Advanced API server is online:
```json
<action name="mcp" tool="nina_ensure_running">{}</action>
```

### 1. General System & Device Telemetry Report
```json
<action name="mcp" tool="nina_get_system_status">{}</action>
```

### 2. Slew Mount & Start Guiding
```json
<action name="mcp" tool="nina_mount_slew">
{
  "ra": 0.7123,
  "dec": 41.269,
  "slew_and_center": true
}
</action>
```

### 3. Capture Light Sub-Exposure & Get Statistics
```json
<action name="mcp" tool="nina_camera_capture">
{
  "duration": 60.0,
  "gain": 100,
  "save": true,
  "target_name": "M31_Andromeda",
  "image_type": "LIGHT",
  "get_result": true,
  "solve": true
}
</action>
```

### 4. Trigger Autofocus Routine
```json
<action name="mcp" tool="nina_focuser_autofocus">{}</action>
```

### 5. Create & Load Calibration Frame Sequence (Darks, Flats, Biases)
```json
<action name="mcp" tool="nina_create_calibration_sequence">
{
  "image_type": "DARK",
  "count": 15,
  "exposure_time": 60.0
}
</action>
```

