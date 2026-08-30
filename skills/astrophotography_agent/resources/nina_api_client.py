"""Lightweight REST client for Tiny Steward to communicate with N.I.N.A's Advanced API plugin.

Supports local IP endpoints and remote HTTPS endpoints served via Caddy reverse proxies & DDNS.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
import httpx


class NinaAPIClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        # Fall back to NINA_BASE_URL env var, or default local N.I.N.A port 1888
        default_url = os.environ.get("NINA_BASE_URL") or "http://127.0.0.1:1888/v2/api"
        self.base_url = (base_url or default_url).rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def get(self, endpoint: str, **params: Any) -> Dict[str, Any]:
        """Perform GET request against N.I.N.A Advanced API envelope."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        clean_params = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get(url, params=clean_params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("Success", False):
            raise RuntimeError(f"N.I.N.A API Error: {data.get('Error', 'Unknown failure')}")
        return data.get("Response")

    def get_system_status(self) -> Dict[str, Any]:
        """Get aggregated system status across all equipment."""
        try:
            return self.get("/equipment/info")
        except Exception as e:
            return {"error": str(e), "connected": False}

    def capture_image(
        self,
        duration: float,
        target_name: Optional[str] = None,
        image_type: str = "LIGHT",
        gain: Optional[int] = None,
        save: bool = True,
    ) -> Dict[str, Any]:
        """Capture single sub-exposure."""
        return self.get(
            "/equipment/camera/capture",
            duration=duration,
            targetName=target_name,
            imageType=image_type,
            gain=gain,
            save=save,
            waitForResult=True,
            getResult=True,
            omitImage=True,
        )


if __name__ == "__main__":
    client = NinaAPIClient()
    print(f"Connecting to N.I.N.A API at: {client.base_url}")
