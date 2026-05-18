"""Lab log and red-team report writers (JSON + markdown summary)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class LabReportMeta:
    path: Path
    title: str
    created_iso: str
    kind: str


def ensure_log_dir(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def write_scan_log(
    log_dir: Path,
    *,
    networks: list[dict[str, Any]],
    source: str,
    mood: str,
    scan_kind: str = "passive_scan",
) -> Path:
    ensure_log_dir(log_dir)
    path = log_dir / f"scan_{_stamp()}.json"
    payload = {
        "type": scan_kind,
        "ts": time.time(),
        "source": source,
        "mood": mood,
        "network_count": len(networks),
        "networks": networks,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_red_team_report(
    log_dir: Path,
    *,
    target_bssid: str,
    actions: list[dict[str, Any]],
    simulated: bool,
    scope_reason: str,
) -> Path:
    ensure_log_dir(log_dir)
    base = log_dir / f"redteam_{_stamp()}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    payload = {
        "type": "red_team_exercise",
        "ts": time.time(),
        "target_bssid": target_bssid,
        "simulated": simulated,
        "scope_reason": scope_reason,
        "actions": actions,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# ByteDog WiFi Lab — Red Team Report",
        "",
        f"- **Target BSSID:** `{target_bssid}`",
        f"- **Simulated:** {simulated}",
        f"- **Scope:** {scope_reason}",
        "",
        "## Actions",
        "",
    ]
    for i, act in enumerate(actions, 1):
        lines.append(f"{i}. **{act.get('name', 'action')}** — {act.get('status', '?')}")
        if detail := act.get("detail"):
            lines.append(f"   - {detail}")
        if cmd := act.get("command"):
            lines.append(f"   - Command: `{cmd}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path


def list_reports(log_dir: Path, *, limit: int = 16) -> list[LabReportMeta]:
    """One entry per report (JSON only — markdown siblings omitted from the list)."""
    if not log_dir.is_dir():
        return []
    seen_stems: set[str] = set()
    files = sorted(
        (p for p in log_dir.iterdir() if p.is_file() and p.suffix == ".json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[LabReportMeta] = []
    for path in files:
        stem = path.stem
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        if path.name.startswith("scan_"):
            kind = "scan"
            label = "Passive scan"
        elif path.name.startswith("redteam_"):
            kind = "red_team"
            label = "Red team"
        else:
            kind = "log"
            label = "Lab log"
        created = time.strftime(
            "%Y-%m-%d %H:%M",
            time.localtime(path.stat().st_mtime),
        )
        out.append(
            LabReportMeta(
                path=path,
                title=f"{label} · {stem}",
                created_iso=created,
                kind=kind,
            )
        )
        if len(out) >= limit:
            break
    return out


def report_preview_lines(path: Path, *, max_lines: int = 5) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ["(unreadable)"]
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return ["(invalid JSON)"]
        rtype = data.get("type", "log")
        if rtype in ("passive_scan", "live_scan"):
            n = data.get("network_count", 0)
            src = data.get("source", "?")
            lines = [
                f"Scan OK · {n} network(s) · backend {src}",
                f"Mood: {data.get('mood', '—')}",
            ]
            nets = data.get("networks") or []
            if isinstance(nets, list) and nets:
                sample = nets[0]
                if isinstance(sample, dict):
                    lines.append(
                        f"Example: {sample.get('ssid', '?')} · {sample.get('bssid', '?')}"
                    )
            return lines
        if rtype == "red_team_exercise":
            lines = [
                f"Target: {data.get('target_bssid', '—')}",
                f"Simulated: {data.get('simulated', '?')}",
                f"Scope: {str(data.get('scope_reason', ''))[:72]}",
            ]
            for act in (data.get("actions") or [])[:3]:
                lines.append(
                    f"· {act.get('name', '?')}: {act.get('status', '?')}"
                )
            return lines[:max_lines]
        return [f"{rtype} log"]
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    return lines[:max_lines] if lines else ["(empty)"]
