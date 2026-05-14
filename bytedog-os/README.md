# ByteDog OS — Phase 1 + Phase 2 foundation

**ByteDog OS** is a **cyberpunk handheld launcher** for **Raspberry Pi 4** (and desktop dev), built with **Python** and **Pygame**. It is meant to feel like a **small console + hacker gadget**, not a Linux desktop or a generic emulator frontend. The mascot is **Chicha**, a dachshund.

Phase 1 delivers a **stable launcher shell**: semantic input (keyboard + SDL gamepads), SQLite pet state, Chicha visuals, audio, splash + health checks, settings, confirmations for quit/shutdown, and performance-minded rendering.

**Phase 2 foundation** (current): code is split into **`src/services/input/`**, **`src/config/`** (multi-file JSON + loader), **`src/core/`** (timing, lifecycle), **`src/pet/mood.py`** / **`behavior.py`**, **`src/ui/transitions.py`** / **`widgets.py`**, without changing player-facing behavior.

**Still out of scope:** RetroPie wiring, real network tools, GPIO, touchscreen, AI/chatbots, Electron/web stacks.

---

## Architecture (high level)

| Area | Location | Notes |
|------|----------|--------|
| App orchestrator | `src/app.py` | Main loop, intents, render dispatch (smaller than pre-refactor) |
| Config | `config/*.json` + `src/config/loader.py` | `app.json` + optional `input.json`, `pet.json`, `ui.json` merged |
| Input (SDL2) | `src/services/input/` | `actions`, `keyboard`, `joystick`, `state`, `debug`, `manager` |
| Input compat | `src/services/input_service.py` | Re-exports `InputService` / `InputAction` |
| Core helpers | `src/core/` | `timing`, `lifecycle`, `scene_manager`, `app_state` |
| Pet | `src/pet/` | `state`, `animations` (Chicha poses), `mood`, `behavior` (placeholder) |
| UI | `src/ui/` | `handheld_shell`, `screens`, `theme`, `debug_overlay`, `transitions`, `widgets` |
| Audio | `src/services/audio.py` | Preloaded `Sound`s; `play_move` aliases `play_menu_move` |
| Data | `src/storage/` | SQLite |

---

## Quick start

```bash
cd bytedog-os
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

- **`data/bytedog.db`** is created on first run (see `.gitignore`).
- **`assets/`** subfolders are ensured at startup.
- On **Pi**, set `"window": { "fullscreen": true }` in `config/app.json` and tune `config/ui.json` → `performance.chicha_fast_scale` if needed.

---

## Configuration

| File | Role |
|------|------|
| `config/app.json` | App name, resolution, FPS, paths, startup/shutdown, audio volume |
| `config/input.json` | Deadzone, repeat cooldowns, axis indices, **PS4-style `mappings`** |
| `config/pet.json` | Chicha timings + `clips` overrides (merged into runtime `chicha` dict) |
| `config/ui.json` | Optional `performance` overrides (vsync, `ambient_mote_count`, `chicha_fast_scale`, `system_poll_sec`) |

Legacy single-file setups still work if you keep everything in `app.json` only; the loader merges optional files **on top** of defaults + `app.json`.

---

## Controls

| Action | Keyboard | PS4 (default SDL mapping) |
|--------|----------|---------------------------|
| Navigate | Arrows or **W A S D** | D-pad (hat / buttons **11–14**) + **left stick** |
| Confirm | **Enter** / **Space** | **Cross** — button **0** |
| Back | **Escape** | **Circle** — button **1** |
| Debug overlay | **F3** | (keyboard) |

Optional **`input.dpad_horizontal_axis` / `dpad_vertical_axis`** (≥ `0`) map a **second axis pair** when the D-pad is axes instead of a hat.

Set **`input.debug`: true** for throttled stdout logs while tuning.

---

## Chicha assets

Under `assets/chicha/<mood>/` place **one primary PNG per mood** (e.g. `idle/chicha-idle.png`).  
Optional `frame_*.png` strips are ignored when a non-`frame_` PNG exists.  
Per-folder overrides: `config/pet.json` → `clips.<mood>.file` → filename inside that folder.

**Ambient behavior** (when clips load): random idle pauses, soft “blink” band on idle, **happy** briefly after menu navigation, **sleep** after `sleep_after_idle_ms` on the launcher (defaults in `pet.json`). Tune `nav_happy_ms` / `sleep_after_idle_ms`.

---

## Sounds (optional files)

Under `assets/sounds/`:

| Role | Preferred path |
|------|------------------|
| Menu move | `navigation/menu-change.mp3` (or `.wav`) |
| Confirm | `actions/selected-item.mp3` / `confirm.wav` |
| Back | `actions/back.wav` / `.mp3` |
| Startup | `system/startup.mp3` / `.wav` |
| Shutdown | `system/shutdown.mp3` / `.wav` |

Missing files are skipped; the app does not crash.

---

## Debugging controllers

1. Press **F3** for the on-screen overlay: FPS, joystick count, names, last semantic action, raw button/axis/hat, current menu selection.
2. Set **`input.debug`: true** in `config/input.json` for throttled stdout traces while tuning mappings.

---

## Benchmarking FPS on Raspberry Pi 4

1. Run fullscreen at target resolution with `chicha_fast_scale` on/off and compare the **F3** FPS readout.
2. Keep **`system_poll_sec`** at `1.0` or higher to avoid extra `/proc` work.
3. Prefer cached assets: Chicha and menu art use cached scaled surfaces where applicable.

---

## Validate Phase 2 foundation (no hardware)

```bash
python tools/validate_phase2_foundation.py
```

Requires **`pip install -r requirements.txt`** (needs **pygame**). The script sets `SDL_VIDEODRIVER=dummy` before importing pygame-dependent code (safe on headless CI). Checks: config files exist, **`src.app` imports**, merged config loads, input module, SQLite init, asset dirs, pygame init + Chicha draw.

---

## Project tree (source, simplified)

```
bytedog-os/
├── main.py
├── requirements.txt
├── config/
│   ├── app.json
│   ├── input.json
│   ├── pet.json
│   └── ui.json
├── tools/
│   ├── validate_phase2_foundation.py
│   └── gen_menu_icons.py
├── assets/
├── data/
└── src/
    ├── app.py
    ├── config/
    ├── core/
    ├── pet/
    ├── services/
    │   ├── input/          # modular input
    │   ├── input_service.py  # compat re-exports
    │   └── …
    ├── startup/
    ├── storage/
    └── ui/
```

Regenerate simple **menu PNG icons** (optional):  
`SDL_VIDEODRIVER=dummy python tools/gen_menu_icons.py`

Main menu hero art: **`assets/images/chicha-deck-bg.png`**. Menu row icons: matching **`*.png`** names in `assets/images/`.

---

## Confirm no input regression (manual)

1. Keyboard: menu wrap, Enter, Esc, F3 overlay.
2. PS4: D-pad + stick navigation, Cross/Circle, hotplug USB.
3. `input.debug` stdout: no axis spam flood; single semantic action per hat edge.

---

## Phase 2 foundation checklist

- [ ] `python tools/validate_phase2_foundation.py` passes.
- [ ] `python main.py`: splash, launcher, settings, quit confirm, **Apagar** confirm, shutdown.
- [ ] F3 overlay shows FPS + joystick lines.
- [ ] ~60 FPS on Pi 4 with defaults.

### Phase 1 regression smoke (still required)

- [ ] Keyboard: arrows / WASD, Enter/Space, Esc, F3.
- [ ] PS4: D-pad (hat and/or buttons), left stick, Cross confirm, Circle back.
- [ ] Hotplug: connect/disconnect without crash or joystick init loops.
- [ ] Menu circular wrap; Chicha draws or safe fallback if assets missing.
- [ ] SQLite auto-created; `.gitignore` keeps DB out of git.

---

## What not to add yet

RetroPie as an integrated product, real offensive security tools, GPIO drivers, cloud AI, heavy UI frameworks.

---

## License

Add your preferred license here.
