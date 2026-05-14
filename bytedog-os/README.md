# ByteDog OS — Phase 1

**ByteDog OS** is a **cyberpunk handheld launcher** for **Raspberry Pi 4** (and desktop dev), built with **Python** and **Pygame**. It is meant to feel like a **small console + hacker gadget**, not a Linux desktop or a generic emulator frontend. The mascot is **Chicha**, a dachshund.

Phase 1 delivers a **stable, polished launcher shell**: input → semantic actions, SQLite pet state, Chicha animation (with fallbacks), audio, splash + health checks, settings, and performance-minded rendering.

**Out of scope for Phase 1:** RetroPie wiring, real network tools, GPIO, touchscreen, AI/chatbots, heavy frameworks.

---

## Quick start (clean machine)

```bash
cd bytedog-os
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

- **`data/bytedog.db`** is created automatically on first run (see `.gitignore`; do not commit DBs).
- **`assets/`** subfolders (`fonts`, `sounds`, `images`, `chicha/...`) are created at startup as needed.
- On **Pi**, set `"window": { "fullscreen": true }` in `config/app.json` and consider `"chicha_fast_scale": true` under `performance` for extra FPS headroom.

---

## Controls

| Action | Keyboard | PS4 (default SDL mapping) |
|--------|----------|---------------------------|
| Menu up / down / left / right | Arrow keys or **W A S D** | **D-pad** (hat or buttons 11–14) + **left stick** |
| Confirm | **Enter** or **Space** | **Cross (X)** — button **0** |
| Back | **Escape** | **Circle** — button **1** |
| Debug overlay | **F3** | **F3** (keyboard) |

Optional **`input.dpad_horizontal_axis` / `dpad_vertical_axis`** (≥ `0`) enable a **second axis pair** when the D-pad is reported as axes instead of a hat.

Set **`"input": { "debug": true }`** for throttled axis/button logs on stdout (useful over SSH).

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

## Chicha sprites

Folder layout:

```
assets/chicha/
├── idle/frame_00.png  frame_01.png  …
├── happy/
├── sleep/
└── alert/
```

- Frames: **`frame_*.png`** (sorted by number) or any **`*.png`** in the folder if no `frame_*` files.
- Per-mood FPS: `config/app.json` → `chicha.clips.<mood>.fps` and `chicha.default_fps`.
- **Ambient behavior** (when clips exist): random idle pauses, soft “blink” band on idle, **happy** clip briefly after **menu navigation**, **sleep** clip after **`sleep_after_idle_ms`** of launcher inactivity (default 120s). Tune with `chicha.nav_happy_ms` and `chicha.sleep_after_idle_ms`.
- If nothing loads: **vector placeholder** dachshund is drawn.

Regenerate simple **menu PNG icons** (optional):  
`SDL_VIDEODRIVER=dummy python tools/gen_menu_icons.py`

Main menu hero art: **`assets/images/chicha-deck-bg.png`**. Menu row icons: matching **`*.png`** names in `assets/images/` (see repo).

---

## Configuration (`config/app.json`)

| Block | Purpose |
|-------|---------|
| `window` | `width`, `height`, `fullscreen`, `title` |
| `fps` | Main loop cap (e.g. 60) |
| `paths` | `assets`, `data` (relative to project root) |
| `chicha` | `default_fps`, `clips`, `sleep_after_idle_ms`, `nav_happy_ms` |
| `performance` | `display_vsync`, `chicha_fast_scale`, `system_poll_sec` |
| `startup` | Splash: `show_splash`, `minimum_splash_ms`, `fail_on_critical` |
| `shutdown` | `minimum_display_ms` (hold after **Apagar**) |
| `input` | `deadzone`, cooldowns, stick axes, optional D-pad axes, `mappings` (PS4: confirm **0**, back **1**, D-pad **11–14**) |

---

## Debugging controllers (no terminal)

1. Press **F3** for the on-screen overlay: FPS, joystick count, names, last semantic action, raw button/axis/hat, current menu selection.
2. Enable **`input.debug`** for stdout traces while tuning mappings.

---

## Benchmarking FPS on Raspberry Pi 4

1. Run fullscreen at target resolution with `chicha_fast_scale` on/off and compare **F3 FPS** readout.
2. Keep **`system_poll_sec`** at `1.0` or higher to avoid extra `/proc` work.
3. Prefer **cached** assets: avoid swapping large PNGs every frame; Chicha and menu icons scale with cached surfaces where applicable.

---

## Project tree (source)

```
bytedog-os/
├── .gitignore
├── main.py
├── requirements.txt
├── config/app.json
├── tools/gen_menu_icons.py
├── assets/               # sounds, images, chicha (created as needed)
├── data/                 # bytedog.db at runtime (gitignored)
└── src/
    ├── app.py
    ├── pet/              # ChichaAnimator, PetState
    ├── services/         # input, audio, wifi, battery, system, …
    ├── startup/          # splash, health_checks
    ├── storage/          # SQLite
    └── ui/               # handheld shell, menu, settings, debug, …
```

---

## Phase 1 completion checklist

Use this to sign off Phase 1 before Phase 2:

- [ ] Clean venv + `pip install -r requirements.txt`; **`python main.py`** runs.
- [ ] Splash + health rows; **FAIL** blocks when configured; **≥ 1.5 s** minimum splash.
- [ ] Keyboard: arrows / WASD, Enter/Space, Esc, F3.
- [ ] PS4: D-pad (hat and/or buttons), **left stick**, **X** confirm, **Circle** back.
- [ ] No input spam: deadzone, edge detection, cooldowns.
- [ ] Hotplug: connect/disconnect **no crash**, no joystick init loops.
- [ ] Menu **circular** wrap; **F3** overlay; **Chicha** animates or **placeholder** if assets missing.
- [ ] Audio safe when files missing; **startup** + optional **shutdown** flow.
- [ ] SQLite auto-created; **`.gitignore`** keeps DB and caches out of git.
- [ ] **~60 FPS** target on Pi 4 with sane defaults.

---

## What not to add before Phase 2

- RetroPie / emulator backends as integrated products  
- Real pentest / network tooling  
- GPIO / touch drivers  
- Cloud AI / chatbots  
- Large UI frameworks  

Phase 2 should **build on** this shell (emulators, GPIO, networking) **without** replacing the input/action model or the lightweight render path.

---

## License

Add your preferred license here.
