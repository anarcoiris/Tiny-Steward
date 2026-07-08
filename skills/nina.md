---
name: nina
type: skill
requires: []
provides: [nina-control, astronomy-capture, telescope-control]
tags: [nina, astronomy, telescope, camera, capture, mount, scheduler]
related: [mcp]
---

# N.I.N.A. (Nighttime Imaging 'N' Astronomy) Control

Control astronomical equipment connected to N.I.N.A. via the `nina-mcp` server.

## Usage

Use the `mcp` action to call registered tools. The body of the action must be a JSON object containing the tool arguments.

### Camera Capture

To capture an exposure:
```xml
<action name="mcp" tool="nina_camera_capture">
{
  "duration": 10.0,
  "save": true,
  "target_name": "M31",
  "image_type": "LIGHT",
  "solve": false
}
</action>
```

Key arguments for `nina_camera_capture`:
- `duration`: exposure length in seconds (float).
- `gain`: camera gain (int, optional).
- `save`: whether to save the image (bool).
- `target_name`: target name for the filename (str, optional).
- `image_type`: "LIGHT", "DARK", "FLAT", or "BIAS" (str).
- `solve`: plate-solve the image (bool).

### Equipment Info

To query camera or mount status:
```xml
<action name="mcp" tool="nina_camera_info"></action>
<action name="mcp" tool="nina_mount_info"></action>
<action name="mcp" tool="nina_get_all_equipment_info"></action>
```

### Mount Slew

To slew the telescope mount to coordinates:
```xml
<action name="mcp" tool="nina_mount_slew">
{
  "ra": 10.5,
  "dec": 41.2
}
</action>
```
*Note: RA is specified in hours, Dec is specified in degrees.*

### Target Scheduler DB

To view or manage Target Scheduler SQLite tables (if enabled):
```xml
<action name="mcp" tool="ts_list_tables"></action>
<action name="mcp" tool="ts_read_table">
{
  "table": "Projects"
}
</action>
```
