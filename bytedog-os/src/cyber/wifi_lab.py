"""WiFi Lab controller: passive scan, Chicha moods, gated red-team exercises."""

from __future__ import annotations

import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from src.cyber import reports as reports_mod
from src.cyber import scan_backends
from src.cyber import scope as scope_mod
from src.cyber import simulations as sim_mod
from src.cyber import toolchain as toolchain_mod
from src.pet.chicha_life import ChichaLifeState


class WifiLabMood(str, Enum):
    CURIOUS = "curious"
    ALERT = "alert"
    SLEEPY = "sleepy"
    HAPPY = "happy"
    IDLE = "idle"


def mood_to_life_state(mood: WifiLabMood) -> ChichaLifeState | None:
    mapping = {
        WifiLabMood.CURIOUS: ChichaLifeState.CURIOUS,
        WifiLabMood.ALERT: ChichaLifeState.ALERT,
        WifiLabMood.SLEEPY: ChichaLifeState.SLEEPY,
        WifiLabMood.HAPPY: ChichaLifeState.HAPPY,
    }
    if mood is WifiLabMood.IDLE:
        return None
    return mapping.get(mood)


@dataclass(frozen=True, slots=True)
class WifiNetwork:
    ssid: str
    bssid: str
    channel: int
    rssi: int
    source: str = "scan"
    synthetic_bssid: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ssid": self.ssid,
            "bssid": self.bssid,
            "channel": self.channel,
            "rssi": self.rssi,
            "source": self.source,
            "synthetic_bssid": self.synthetic_bssid,
        }


class WifiLabPanel(Enum):
    HOME = auto()
    LAB = auto()
    RED_WARNING = auto()
    RED_TEAM = auto()
    REPORTS = auto()
    GUIDE = auto()


class RedTeamAction(Enum):
    LIVE_SCAN = auto()
    DEAUTH = auto()
    ROAMING = auto()
    HANDSHAKE = auto()
    OFFENSIVE = auto()
    RUN_ALL = auto()


@dataclass(slots=True)
class WifiLabController:
    root: Path
    cfg: dict[str, Any]
    panel: WifiLabPanel = WifiLabPanel.HOME
    home_index: int = 0
    lab_focus_scan: bool = True
    lab_network_index: int = 0
    red_action_index: int = 0
    red_target_index: int = 0
    red_focus_scan: bool = True
    red_warning_ack: bool = False
    red_confirm_hold: bool = False
    mood: WifiLabMood = WifiLabMood.SLEEPY
    networks: list[WifiNetwork] = field(default_factory=list)
    scanning: bool = False
    last_scan_mono: float = 0.0
    last_scan_source: str = ""
    idle_ms: float = 0.0
    status_message: str = ""
    last_log_path: Path | None = None
    report_index: int = 0
    _reports_cache: list[reports_mod.LabReportMeta] = field(default_factory=list)
    _toolchain: toolchain_mod.LabToolchain | None = None

    @property
    def log_dir(self) -> Path:
        rel = str(self.cfg.get("log_dir", "data/lab_logs"))
        return self.root / rel

    @property
    def toolchain(self) -> toolchain_mod.LabToolchain:
        if self._toolchain is None:
            self._toolchain = toolchain_mod.build_toolchain(self.cfg)
        return self._toolchain

    @property
    def dangerous_enabled(self) -> bool:
        return bool(self.cfg.get("dangerous_actions_enabled", False))

    @property
    def red_team_available(self) -> bool:
        return bool(self.cfg.get("enabled", True)) and bool(self.cfg.get("red_team_mode", True))

    def tick(self, dt_ms: float) -> None:
        self.idle_ms += max(0.0, dt_ms)
        if self.scanning:
            return
        if self.networks and self.mood not in (WifiLabMood.HAPPY, WifiLabMood.ALERT):
            self.mood = WifiLabMood.CURIOUS
        elif not self.networks and self.idle_ms > 8000.0:
            self.mood = WifiLabMood.SLEEPY
        elif not self.networks:
            self.mood = WifiLabMood.IDLE

    def chicha_life_override(self) -> ChichaLifeState | None:
        return mood_to_life_state(self.mood)

    def home_items(self) -> list[str]:
        items = ["Lab Mode", "Reports", "WPA/WPA2 Guide", "Back to Cyberdeck"]
        if self.red_team_available:
            items.insert(1, "Red Team Mode")
        return items

    def refresh_reports(self) -> None:
        self._reports_cache = reports_mod.list_reports(self.log_dir)

    @property
    def reports(self) -> list[reports_mod.LabReportMeta]:
        return self._reports_cache

    def enter_panel(self, panel: WifiLabPanel) -> None:
        self.panel = panel
        self.status_message = ""
        if panel is WifiLabPanel.REPORTS:
            self.refresh_reports()
            self.report_index = 0
        if panel is WifiLabPanel.RED_WARNING:
            self.red_warning_ack = False
            self.red_confirm_hold = False
        if panel is WifiLabPanel.RED_TEAM:
            self.red_focus_scan = True
            self.red_action_index = 0

    def start_passive_scan(self, *, live: bool = False) -> None:
        if self.scanning:
            return
        self.scanning = True
        self.mood = WifiLabMood.CURIOUS
        label = "live" if live else "passive"
        self.status_message = f"Scanning ({label})…"
        self.idle_ms = 0.0

        scan_rows, source = scan_backends.run_scan()
        if scan_rows:
            results = [ScanResult_to_network(r) for r in scan_rows]
        else:
            results = [
                ScanResult_to_network(ScanResult_from_sim(s))
                for s in sim_mod.simulated_scan_networks()
            ]
            source = "simulation"

        self.networks = results
        self.last_scan_source = source
        self.scanning = False
        self.last_scan_mono = time.monotonic()
        self._update_mood_after_scan()

        scan_kind = "live_scan" if live else "passive_scan"
        path = reports_mod.write_scan_log(
            self.log_dir,
            networks=[n.as_dict() for n in self.networks],
            source=source,
            mood=self.mood.value,
            scan_kind=scan_kind,
        )
        self.last_log_path = path
        sim_note = " (demo data)" if source == "simulation" else ""
        self.status_message = (
            f"{label.capitalize()} scan · {len(self.networks)} AP(s) · {source}{sim_note}"
        )
        self.refresh_reports()

    def start_red_team_live_scan(self) -> None:
        self.start_passive_scan(live=True)

    def _update_mood_after_scan(self) -> None:
        if not self.networks:
            self.mood = WifiLabMood.SLEEPY
            return
        channels = [n.channel for n in self.networks if n.channel > 0]
        if channels:
            counts = Counter(channels)
            if max(counts.values()) >= 3:
                self.mood = WifiLabMood.ALERT
                return
        self.mood = WifiLabMood.HAPPY

    def selected_network(self) -> WifiNetwork | None:
        if not self.networks:
            return None
        idx = max(0, min(self.lab_network_index, len(self.networks) - 1))
        return self.networks[idx]

    def red_team_target(self) -> WifiNetwork | None:
        if not self.networks:
            return None
        idx = max(0, min(self.red_target_index, len(self.networks) - 1))
        return self.networks[idx]

    def red_team_actions(self) -> list[str]:
        return [
            "Live scan",
            "Deauthentication (lab)",
            "Roaming collection",
            "Handshake capture",
            "Offensive command",
            "Run full exercise + report",
        ]

    def scan_status_line(self) -> str:
        if self.scanning:
            return "Scan in progress…"
        if not self.networks:
            return "No APs loaded · run Live scan or Lab scan"
        n = len(self.networks)
        src = self.last_scan_source or "unknown"
        if src == "simulation":
            return f"Demo data only · {n} fake AP(s) · no OS WiFi backend"
        synth = sum(1 for net in self.networks if net.synthetic_bssid)
        if src == "corewlan":
            if synth:
                return (
                    f"Scan OK · {n} AP(s) via CoreWLAN (real names) · "
                    "macOS hides BSSID — mapped IDs for lab UI"
                )
            return f"Scan OK · {n} AP(s) via CoreWLAN · real SSID + BSSID"
        if synth:
            return (
                f"Scan OK · {n} AP(s) via {src} · "
                f"SSID/channel real · BSSID mapped ({synth})"
            )
        return f"Scan OK · {n} AP(s) via {src}"

    def attack_status_line(self) -> str:
        tc = self.toolchain
        if not self.dangerous_enabled:
            return "Attacks blocked · set dangerous_actions_enabled: true"
        if tc.os_name == "Darwin" and tc.can_live_deauth:
            return (
                f"Deauth uses aireplay-ng on {tc.monitor_iface} · "
                "often fails on Mac WiFi · use Pi for real frames · "
                + tc.tools_line()
            )
        if tc.can_live_attack:
            return f"Live deauth + capture · iface {tc.monitor_iface} · {tc.tools_line()}"
        if tc.can_live_deauth:
            return f"Live deauth ready · {tc.tools_line()} · capture still simulated"
        if tc.can_live_capture:
            return f"Live capture only · install aireplay-ng for deauth"
        if tc.os_name == "Darwin":
            return "Tools not found · brew install aircrack-ng (check /opt/homebrew/sbin)"
        return "Tools not found · sudo apt install aircrack-ng on Pi"

    def ui_banner_lines(self) -> list[str]:
        lines = [self.scan_status_line()]
        if self.panel in (WifiLabPanel.RED_TEAM, WifiLabPanel.RED_WARNING):
            lines.append(self.attack_status_line())
        tgt = self.red_team_target() if self.networks else None
        if tgt and self.panel is WifiLabPanel.RED_TEAM:
            if tgt.synthetic_bssid:
                tag = " · BSSID mapped (use SSID on Pi for live deauth)"
            else:
                tag = ""
            lines.append(f"Target AP: {tgt.ssid} · {tgt.bssid}{tag}")
        return lines

    def acknowledge_red_warning(self) -> None:
        self.red_warning_ack = True

    def confirm_red_team(self) -> None:
        self.red_confirm_hold = True

    def run_red_team_action(self, action: RedTeamAction) -> str:
        target = self.red_team_target()
        if target is None:
            self.status_message = "Run Live scan and select a target AP."
            return self.status_message

        scope = scope_mod.check_red_team_scope(
            self.cfg,
            target_bssid=target.bssid,
            dangerous_enabled=self.dangerous_enabled,
        )
        tc = self.toolchain
        needs_deauth = action in (
            RedTeamAction.DEAUTH,
            RedTeamAction.OFFENSIVE,
            RedTeamAction.RUN_ALL,
        )
        needs_capture = action in (
            RedTeamAction.ROAMING,
            RedTeamAction.HANDSHAKE,
            RedTeamAction.RUN_ALL,
        )
        use_simulation = scope.simulated or (
            (needs_deauth and not tc.can_live_deauth)
            or (needs_capture and not tc.can_live_capture)
        )

        if (
            not use_simulation
            and tc.os_name == "Linux"
            and bool(self.cfg.get("auto_monitor_mode", True))
        ):
            ok, detail = toolchain_mod.ensure_monitor_mode(tc)
            if not ok:
                use_simulation = True
                scope = scope_mod.ScopeDecision(
                    False,
                    f"Monitor setup failed: {detail}",
                    simulated=True,
                )

        actions: list[dict[str, str]] = []
        if action in (RedTeamAction.DEAUTH, RedTeamAction.RUN_ALL):
            actions.append(self._deauth(target, use_simulation))
        if action in (RedTeamAction.ROAMING, RedTeamAction.RUN_ALL):
            actions.append(self._roaming(target, use_simulation))
        if action in (RedTeamAction.HANDSHAKE, RedTeamAction.RUN_ALL):
            actions.append(self._handshake(target, use_simulation))
        if action in (RedTeamAction.OFFENSIVE, RedTeamAction.RUN_ALL):
            actions.append(self._offensive(target, use_simulation))

        any_live_ok = any(a.get("status") in ("ok", "timeout") for a in actions)
        any_live_ran = any(a.get("status") not in ("simulated",) for a in actions)

        path = reports_mod.write_red_team_report(
            self.log_dir,
            target_bssid=target.bssid,
            actions=actions,
            simulated=use_simulation,
            scope_reason=scope.reason,
        )
        self.last_log_path = path
        self.mood = WifiLabMood.HAPPY if any_live_ok else WifiLabMood.ALERT
        self.refresh_reports()
        if use_simulation:
            self.status_message = f"Report saved · simulated ({scope.reason[:48]})"
        elif any_live_ok:
            self.status_message = "Live attack OK · report saved"
        elif any_live_ran:
            fail = next(
                (a.get("detail", "") for a in actions if a.get("status") in ("failed", "error")),
                "tool error",
            )
            self.status_message = f"Live tool ran but failed · {fail[:56]}"
        else:
            self.status_message = "Red team exercise complete · report saved"
        return self.status_message

    def _deauth(self, target: WifiNetwork, simulated: bool) -> dict[str, str]:
        tc = self.toolchain
        if simulated or not tc.can_live_deauth:
            return sim_mod.simulate_deauth(
                target.bssid,
                ssid=target.ssid,
                command=toolchain_mod.preview_deauth_command(
                    tc,
                    ssid=target.ssid,
                    bssid=target.bssid,
                    synthetic_bssid=target.synthetic_bssid,
                ),
            )
        cmd = toolchain_mod.deauth_command(
            tc,
            ssid=target.ssid,
            bssid=target.bssid,
            synthetic_bssid=target.synthetic_bssid,
        )
        if cmd is None:
            return sim_mod.simulate_deauth(target.bssid, ssid=target.ssid)
        return _run_argv("deauthentication", cmd)

    def _roaming(self, target: WifiNetwork, simulated: bool) -> dict[str, str]:
        tc = self.toolchain
        prefix = str(self.log_dir / "lab_roam")
        if simulated or not tc.can_live_capture:
            return sim_mod.simulate_roaming_collect(
                target.bssid,
                ssid=target.ssid,
                command=toolchain_mod.preview_roaming_command(
                    tc,
                    ssid=target.ssid,
                    bssid=target.bssid,
                    synthetic_bssid=target.synthetic_bssid,
                    out_prefix=prefix,
                ),
            )
        cmd = toolchain_mod.roaming_capture_command(
            tc,
            ssid=target.ssid,
            bssid=target.bssid,
            synthetic_bssid=target.synthetic_bssid,
            out_prefix=prefix,
        )
        if cmd is None:
            return sim_mod.simulate_roaming_collect(target.bssid, ssid=target.ssid)
        return _run_argv("roaming_collection", cmd, timeout=12.0)

    def _handshake(self, target: WifiNetwork, simulated: bool) -> dict[str, str]:
        tc = self.toolchain
        prefix = str(self.log_dir / "lab_hs")
        if simulated or not tc.can_live_capture:
            return sim_mod.simulate_handshake_capture(
                target.bssid,
                ssid=target.ssid,
                command=toolchain_mod.preview_roaming_command(
                    tc,
                    ssid=target.ssid,
                    bssid=target.bssid,
                    synthetic_bssid=target.synthetic_bssid,
                    out_prefix=prefix,
                ),
            )
        cmd = toolchain_mod.handshake_capture_command(
            tc,
            ssid=target.ssid,
            bssid=target.bssid,
            synthetic_bssid=target.synthetic_bssid,
            out_prefix=prefix,
        )
        if cmd is None:
            return sim_mod.simulate_handshake_capture(target.bssid, ssid=target.ssid)
        return _run_argv("handshake_capture", cmd, timeout=14.0)

    def _offensive(self, target: WifiNetwork, simulated: bool) -> dict[str, str]:
        tc = self.toolchain
        preview = toolchain_mod.preview_deauth_command(
            tc,
            ssid=target.ssid,
            bssid=target.bssid,
            synthetic_bssid=target.synthetic_bssid,
            count=3,
        )
        if simulated or not tc.can_live_deauth:
            return sim_mod.simulate_offensive_shell(preview)
        cmd = toolchain_mod.deauth_command(
            tc,
            ssid=target.ssid,
            bssid=target.bssid,
            synthetic_bssid=target.synthetic_bssid,
            count=3,
        )
        if cmd is None:
            return sim_mod.simulate_offensive_shell(preview)
        return _run_argv("offensive_command", cmd)


def ScanResult_from_sim(s: sim_mod.SimulatedNetwork) -> scan_backends.ScanResult:
    return scan_backends.ScanResult(
        ssid=s.ssid,
        bssid=s.bssid,
        channel=s.channel,
        rssi=s.rssi,
        source="simulation",
        synthetic_bssid=False,
    )


def ScanResult_to_network(r: scan_backends.ScanResult) -> WifiNetwork:
    return WifiNetwork(
        ssid=r.ssid,
        bssid=r.bssid,
        channel=r.channel,
        rssi=r.rssi,
        source=r.source,
        synthetic_bssid=r.synthetic_bssid,
    )


def _run_argv(name: str, argv: list[str], *, timeout: float = 8.0) -> dict[str, str]:
    cmd_s = " ".join(argv)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        detail = (proc.stderr or proc.stdout or "").strip()[:220]
        if proc.returncode == 0:
            status = "ok"
        elif proc.returncode < 0:
            status = "error"
        else:
            status = "failed"
        if not detail and proc.returncode != 0:
            detail = (
                "macOS built-in WiFi cannot inject frames · "
                "use Raspberry Pi + wlan0mon for lab deauth"
            )
        return {
            "name": name,
            "status": status,
            "detail": detail or f"exit {proc.returncode}",
            "command": cmd_s,
        }
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "status": "timeout",
            "detail": f"Capture ran {timeout:.0f}s (check {argv[0]} output in log_dir)",
            "command": cmd_s,
        }
    except OSError as exc:
        return {
            "name": name,
            "status": "error",
            "detail": str(exc),
            "command": cmd_s,
        }
