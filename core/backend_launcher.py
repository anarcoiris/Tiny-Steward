"""Generic backend process launcher from config.yaml llm.*.launch.

Steward does not interpret Docker/scripts — only argv + cwd + health poll
+ optional GET /props verification of F3 host expectations (total_slots).

PowerShell launchers under llamacpp accept ``-Parallel`` / ``-Profile`` /
``-Context``; those map from structured yaml keys. Flags the scripts do not
yet expose (``--cache-ram``, ``--cache-idle-slots``, ``--slot-save-path``)
belong in ``extra_args`` once ops adds them — Steward will not invent a
llama-server CLI rewrite.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from core.config_check import PropsSnapshot, fetch_props

LaneName = str  # "orch" | "atomic"


def normalize_lane(name: str) -> LaneName | None:
    key = (name or "").strip().lower()
    if key in ("orch", "orchestrator"):
        return "orch"
    if key in ("atomic", "atom"):
        return "atomic"
    return None


def _normalize_cmd(cmd: Any) -> list[str] | None:
    if cmd is None:
        return None
    if isinstance(cmd, str):
        parts = cmd.strip().split()
        return parts or None
    if isinstance(cmd, (list, tuple)):
        return [str(x) for x in cmd]
    return None


def _normalize_extra_args(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return raw.strip().split() if raw.strip() else []
    if isinstance(raw, (list, tuple)):
        return [str(x) for x in raw]
    return []


@dataclass
class LaneLaunchConfig:
    cmd: list[str]
    cwd: str | None = None
    autostart: bool = False
    # F3 host knobs (mapped to PowerShell -Parallel / -Profile / -Context)
    parallel: int | None = None
    profile: str | None = None
    context: int | None = None
    extra_args: list[str] = field(default_factory=list)
    # Ops annotations (status/docs only until host scripts accept them)
    cache_ram: str | None = None
    cache_idle_slots: bool | None = None
    slot_save_path: str | None = None
    # After start+health: require GET /props total_slots == this (default=parallel)
    expect_total_slots: int | None = None
    base_url: str | None = None

    def build_argv(self) -> list[str]:
        """cmd + structured F3 params + free-form extra_args."""
        argv = list(self.cmd)
        if self.parallel is not None:
            argv.extend(["-Parallel", str(int(self.parallel))])
        if self.profile:
            argv.extend(["-Profile", str(self.profile)])
        if self.context is not None:
            argv.extend(["-Context", str(int(self.context))])
        if self.extra_args:
            argv.extend(self.extra_args)
        return argv

    def resolved_expect_slots(self) -> int | None:
        if self.expect_total_slots is not None:
            return int(self.expect_total_slots)
        if self.parallel is not None:
            return int(self.parallel)
        return None


@dataclass
class LaneState:
    process: subprocess.Popen | None = None
    pid: int | None = None
    last_error: str | None = None
    last_props: PropsSnapshot | None = None


HealthFn = Callable[[], bool]


class BackendLauncher:
    """start / stop / status / props for orch and atomic launch blocks."""

    def __init__(
        self,
        configs: dict[LaneName, LaneLaunchConfig | None],
        health: dict[LaneName, HealthFn | None] | None = None,
        *,
        ready_timeout: float = 90.0,
        poll_interval: float = 1.5,
        gate_slots: dict[LaneName, int] | None = None,
    ):
        self.configs = configs
        self.health = health or {}
        self.ready_timeout = ready_timeout
        self.poll_interval = poll_interval
        self.gate_slots = gate_slots or {}
        self._state: dict[LaneName, LaneState] = {
            "orch": LaneState(),
            "atomic": LaneState(),
        }

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        orch_health: HealthFn | None = None,
        atomic_health: HealthFn | None = None,
    ) -> "BackendLauncher":
        llm = config.get("llm") or {}
        gate = ((config.get("backends") or {}).get("gate") or {})
        configs: dict[LaneName, LaneLaunchConfig | None] = {
            "orch": cls._parse_launch(llm.get("orchestrator") or {}, lane="orch"),
            "atomic": cls._parse_launch(llm.get("atomic") or {}, lane="atomic"),
        }
        gate_slots: dict[LaneName, int] = {}
        if gate.get("orch_slots") is not None:
            gate_slots["orch"] = int(gate["orch_slots"])
        if gate.get("atomic_slots") is not None:
            gate_slots["atomic"] = int(gate["atomic_slots"])
        return cls(
            configs,
            health={"orch": orch_health, "atomic": atomic_health},
            gate_slots=gate_slots,
        )

    @staticmethod
    def _parse_launch(lane_cfg: dict[str, Any], *, lane: LaneName) -> LaneLaunchConfig | None:
        block = lane_cfg.get("launch")
        if not isinstance(block, dict):
            return None
        cmd = _normalize_cmd(block.get("cmd"))
        if not cmd:
            return None
        cwd = block.get("cwd")
        parallel = block.get("parallel")
        context = block.get("context")
        expect = block.get("expect_total_slots")
        cache_idle = block.get("cache_idle_slots")
        return LaneLaunchConfig(
            cmd=cmd,
            cwd=str(cwd) if cwd else None,
            autostart=bool(block.get("autostart", False)),
            parallel=int(parallel) if parallel is not None else None,
            profile=str(block["profile"]) if block.get("profile") else None,
            context=int(context) if context is not None else None,
            extra_args=_normalize_extra_args(block.get("extra_args")),
            cache_ram=str(block["cache_ram"]) if block.get("cache_ram") is not None else None,
            cache_idle_slots=bool(cache_idle) if cache_idle is not None else None,
            slot_save_path=str(block["slot_save_path"]) if block.get("slot_save_path") else None,
            expect_total_slots=int(expect) if expect is not None else None,
            base_url=str(lane_cfg["base_url"]) if lane_cfg.get("base_url") else None,
        )

    def status(self, lane: LaneName) -> dict[str, Any]:
        st = self._state[lane]
        cfg = self.configs.get(lane)
        running = False
        if st.process is not None:
            running = st.process.poll() is None
            if not running:
                st.process = None
        healthy = None
        hf = self.health.get(lane)
        if hf is not None:
            try:
                healthy = bool(hf())
            except Exception:
                healthy = False
        out: dict[str, Any] = {
            "lane": lane,
            "configured": cfg is not None,
            "cmd": list(cfg.cmd) if cfg else None,
            "argv": cfg.build_argv() if cfg else None,
            "cwd": cfg.cwd if cfg else None,
            "autostart": cfg.autostart if cfg else False,
            "parallel": cfg.parallel if cfg else None,
            "profile": cfg.profile if cfg else None,
            "context": cfg.context if cfg else None,
            "expect_total_slots": cfg.resolved_expect_slots() if cfg else None,
            "cache_ram": cfg.cache_ram if cfg else None,
            "cache_idle_slots": cfg.cache_idle_slots if cfg else None,
            "slot_save_path": cfg.slot_save_path if cfg else None,
            "pid": st.pid if running else None,
            "process_running": running,
            "healthy": healthy,
            "last_error": st.last_error,
            "gate_slots": self.gate_slots.get(lane),
        }
        if st.last_props and st.last_props.reachable:
            out["props_total_slots"] = st.last_props.total_slots
            out["props_n_ctx"] = st.last_props.n_ctx
        return out

    def props(self, lane: LaneName) -> dict[str, Any]:
        """Fetch live GET /props and compare to launch expectations."""
        cfg = self.configs.get(lane)
        if not cfg or not cfg.base_url:
            return {"ok": False, "error": f"No base_url for {lane}"}
        snap = fetch_props(cfg.base_url)
        self._state[lane].last_props = snap
        if not snap.reachable:
            return {"ok": False, "error": snap.error or "props unreachable", "reachable": False}

        expect = cfg.resolved_expect_slots()
        messages: list[str] = []
        ok = True
        if expect is not None and snap.total_slots is not None:
            if snap.total_slots != expect:
                ok = False
                messages.append(
                    f"total_slots={snap.total_slots} != expect {expect} "
                    f"(raise host --parallel / launch.parallel or fix expect_total_slots)"
                )
            else:
                messages.append(f"total_slots={snap.total_slots} matches expect")

        gate_n = self.gate_slots.get(lane)
        if gate_n is not None and snap.total_slots is not None and gate_n > snap.total_slots:
            ok = False
            messages.append(
                f"backends.gate slots={gate_n} > total_slots={snap.total_slots}"
            )

        if cfg.cache_ram is not None or cfg.cache_idle_slots is not None:
            messages.append(
                "cache_ram/cache_idle_slots are launch annotations — "
                "confirm on host scripts (--cache-ram / --cache-idle-slots); "
                "not visible on GET /props"
            )
        if cfg.slot_save_path:
            messages.append(
                f"slot_save_path annotated: {cfg.slot_save_path} "
                f"(F4 disk API is host ops; Steward does not call /slots)"
            )

        return {
            "ok": ok,
            "reachable": True,
            "n_ctx": snap.n_ctx,
            "total_slots": snap.total_slots,
            "expect_total_slots": expect,
            "parallel": cfg.parallel,
            "messages": messages,
        }

    def start(self, lane: LaneName, *, wait_healthy: bool = True, verify_props: bool = True) -> dict[str, Any]:
        cfg = self.configs.get(lane)
        if not cfg:
            return {"ok": False, "error": f"No launch config for {lane} (set llm.*.launch in config.yaml)"}

        st = self._state[lane]
        if st.process is not None and st.process.poll() is None:
            out = {"ok": True, "already_running": True, "pid": st.pid, **self.status(lane)}
            if verify_props:
                out["props"] = self.props(lane)
            return out

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

        argv = cfg.build_argv()
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cfg.cwd or None,
                creationflags=creationflags,
            )
        except Exception as e:
            st.last_error = str(e)
            return {"ok": False, "error": str(e), "argv": argv}

        st.process = proc
        st.pid = proc.pid
        st.last_error = None

        if wait_healthy:
            hf = self.health.get(lane)
            if hf is not None:
                deadline = time.monotonic() + self.ready_timeout
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        st.last_error = f"process exited early (code={proc.returncode})"
                        return {"ok": False, "error": st.last_error, "pid": st.pid, "argv": argv}
                    try:
                        if hf():
                            result: dict[str, Any] = {
                                "ok": True,
                                "pid": st.pid,
                                "healthy": True,
                                "argv": argv,
                            }
                            if verify_props:
                                p = self.props(lane)
                                result["props"] = p
                                if not p.get("ok"):
                                    result["ok"] = False
                                    result["error"] = "; ".join(p.get("messages") or [p.get("error", "props mismatch")])
                                    st.last_error = result["error"]
                            return result
                    except Exception:
                        pass
                    time.sleep(self.poll_interval)
                st.last_error = f"timed out waiting for {lane} health ({self.ready_timeout}s)"
                return {"ok": False, "error": st.last_error, "pid": st.pid, "started": True, "argv": argv}

        result = {"ok": True, "pid": st.pid, "healthy": None, "argv": argv}
        if verify_props:
            result["props"] = self.props(lane)
        return result

    def stop(self, lane: LaneName) -> dict[str, Any]:
        st = self._state[lane]
        if st.process is None or st.process.poll() is not None:
            st.process = None
            return {"ok": True, "stopped": False, "reason": "no tracked process"}
        try:
            st.process.terminate()
            try:
                st.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                st.process.kill()
                st.process.wait(timeout=5)
        except Exception as e:
            st.last_error = str(e)
            return {"ok": False, "error": str(e), "pid": st.pid}
        pid = st.pid
        st.process = None
        return {"ok": True, "stopped": True, "pid": pid}
