# ByteDog OS

Status: v0.1.0 Phase 1 complete. Phase 2 in progress.

License: MIT

**ByteDog OS** is a **cyberpunk handheld launcher** for **Raspberry Pi 4** (and desktop dev), built with **Python** and **Pygame**. It is meant to feel like a **small console + hacker gadget**, not a Linux desktop or a generic emulator frontend. The mascot is **Chicha**, a dachshund.

**Phase 1** delivered a stable launcher: semantic input (keyboard + SDL gamepads), SQLite pet state, Chicha visuals, audio, splash + health checks, settings, quit/shutdown confirmations, and performance-minded rendering.

**Phase 2** focuses on **personality and polish** (not feature explosion): Chicha life states + strip timing, lightweight behavior edges, handheld menu feel (cursor lerp, intro fade), richer settings readouts, deterministic audio reactions, and split config. Architecture stays modular (`src/services/input/`, `src/config/`, `src/core/`, `src/pet/`, `src/ui/`).

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
| Pet | `src/pet/` | `state`, `animations` (poses + strips), `mood`, `behavior` (wake / confirm hooks) |
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
| `config/pet.json` | `default_fps`, `blink`, `wake_ack_chance`, sleep/nav timers, `clips` overrides |
| `config/ui.json` | `performance` + **`transitions`** (`enabled`, `launcher_intro_fade_ms`) |

Legacy single-file setups still work if you keep everything in `app.json` only; the loader merges optional files **on top** of defaults + `app.json`.

**Input feel:** edit `config/input.json` (`deadzone`, `repeat_cooldown_ms`, `hat_repeat_ms`, `mappings`). **`input.debug`: true** logs throttled SDL events to stdout.

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

```
assets/chicha/
├── idle/          # hero PNG and/or frame_00.png …
├── happy/
├── sleep/         # maps to “sleepy” life state
├── curious/
├── alert/
├── gaming/
├── low_battery/
└── booting/
```

- **Single hero PNG** (e.g. `idle/chicha-idle.png`): one frame; optional **random blink** (squish) on idle per `pet.json` → `blink`.
- **Strip**: only **`frame_*.png`** files (sorted) → cycles at **`default_fps`** or `clips.<mood>.fps`.
- If both hero and `frame_*` exist, the hero PNG wins (strip ignored).
- **`config/pet.json`**: `clips.<mood>.file` picks an explicit filename; `blink` / `wake_ack_chance` tune idle feel.
- If nothing loads: **vector placeholder** silhouette (cheap primitives).

**Life states** (deterministic): booting at splash, happy on confirm + nav bursts, curious on rapid nav, sleepy after `sleep_after_idle_ms`, gaming after Retro placeholder, low battery from power readout, alert from DB mood keywords.

---

## Sounds (optional files)

Under `assets/sounds/` (preloaded at startup; missing files are skipped):

| Role | Paths tried (first match wins) |
|------|--------------------------------|
| Menu move | **`move.wav`**, then `navigation/menu-change.*`, … |
| Confirm | **`confirm.wav`**, then `actions/selected-item.*`, … |
| Back | **`back.wav`**, then `actions/back.*`, … |
| Startup | **`startup.wav`**, then `system/startup.*`, … |
| Shutdown | `system/shutdown.*`, `actions/shutdown.*`, … |
| Warning | **`warning.wav`**, then `system/warning.*`, … |
| Chicha react | **`chicha_react.wav`**, then `chicha/ack.*`, … |

Missing files or a failed mixer init do **not** crash the app.

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

## Validate Phase 2 (no hardware)

```bash
python tools/validate_phase2.py
```

Requires **`pip install -r requirements.txt`** (needs **pygame**). Sets `SDL_VIDEODRIVER=dummy` before importing pygame code. Checks: config files, **`src.app` import**, merged config, input, SQLite, **`AudioService.initialize()`**, Chicha draw + vector fallback, asset folders.

`tools/validate_phase2_foundation.py` delegates to the same checks (kept for older CI references).

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
│   ├── validate_phase2.py
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

## Phase 2 checklist

- [ ] `python tools/validate_phase2.py` passes.
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

## What not to add yet (save for Phase 3+)

Integrated RetroPie as a full product, real offensive security tooling, GPIO/touch drivers, cloud AI, heavy UI frameworks, and replacing the semantic input model.
