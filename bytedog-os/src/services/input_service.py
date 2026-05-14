"""Handheld-oriented input: keyboard, SDL2 hats/buttons/axes; GPIO hook point."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Final, Iterator

import pygame


class InputAction(Enum):
    """Semantic actions for the launcher shell."""

    MENU_UP = auto()
    MENU_DOWN = auto()
    MENU_LEFT = auto()
    MENU_RIGHT = auto()
    CONFIRM = auto()
    BACK = auto()
    EXIT = auto()
    TOGGLE_DEBUG = auto()


InputIntent = InputAction
MENU_CONFIRM = InputAction.CONFIRM


_DEFAULT_MAPPINGS: Final[dict[str, list[int]]] = {
    "confirm_buttons": [0],
    "back_buttons": [1],
    "exit_buttons": [],
    "menu_up_buttons": [11],
    "menu_down_buttons": [12],
    "menu_left_buttons": [13],
    "menu_right_buttons": [14],
}


def _int_list(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _mapping_sets(cfg: dict[str, Any]) -> dict[str, frozenset[int]]:
    m = dict(_DEFAULT_MAPPINGS)
    user = cfg.get("mappings")
    if isinstance(user, dict):
        for key in _DEFAULT_MAPPINGS:
            if key in user and isinstance(user[key], list):
                m[key] = _int_list(user[key])
    return {k: frozenset(v) for k, v in m.items()}


def _axis_sign(value: float, threshold: float) -> int:
    """-1 = negative deflection, 0 = neutral, 1 = positive deflection."""
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


@dataclass(slots=True)
class _NavAxisState:
    """Per-source axis sign memory for edge detection (-1 / 0 / +1)."""

    h: int = 0
    v: int = 0


class KeyboardAdapter:
    @staticmethod
    def actions_from_keydown(key: int) -> Iterator[InputAction]:
        if key in (pygame.K_UP, pygame.K_w):
            yield InputAction.MENU_UP
        elif key in (pygame.K_DOWN, pygame.K_s):
            yield InputAction.MENU_DOWN
        elif key in (pygame.K_LEFT, pygame.K_a):
            yield InputAction.MENU_LEFT
        elif key in (pygame.K_RIGHT, pygame.K_d):
            yield InputAction.MENU_RIGHT
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            yield InputAction.CONFIRM
        elif key == pygame.K_ESCAPE:
            yield InputAction.BACK
        elif key == pygame.K_F3:
            yield InputAction.TOGGLE_DEBUG


class GPIOAdapter:
    def poll(self) -> Iterator[InputAction]:
        yield from ()


class JoystickAdapter:
    """
    Hats, mapped buttons, left analog stick, optional D-pad axes.

    Axis deflection uses threshold T (config ``deadzone``):
    - value > T  -> sign +1 (DOWN for vertical, RIGHT for horizontal)
    - value < -T -> sign -1 (UP for vertical, LEFT for horizontal)

    Small ``stick_center_deadzone`` snaps near-zero raw values to 0 before T.

    D-pad can arrive as hat, buttons (see mappings), or a second axis pair
    (``dpad_horizontal_axis`` / ``dpad_vertical_axis`` when >= 0).

    Edge detection: per joystick ``instance_id`` and per source (stick vs d-pad
    axes) we store last sign {-1,0,1}. We emit only on transitions; cooldown
    limits repeat rate without advancing sign into a new deflection while blocked.
    """

    def __init__(self, cfg: dict[str, Any], joysticks: dict[int, pygame.joystick.Joystick]) -> None:
        self._joysticks = joysticks
        self._maps = _mapping_sets(cfg)
        self._threshold = float(cfg.get("deadzone", 0.55))
        self._center = float(cfg.get("stick_center_deadzone", 0.12))
        self._repeat_ms = float(cfg.get("repeat_cooldown_ms", 180.0))
        self._hat_repeat_ms = float(cfg.get("hat_repeat_ms", self._repeat_ms))
        self._left_axis_h = int(cfg.get("left_stick_horizontal_axis", 0))
        self._left_axis_v = int(cfg.get("left_stick_vertical_axis", 1))
        self._dpad_axis_h = int(cfg.get("dpad_horizontal_axis", -1))
        self._dpad_axis_v = int(cfg.get("dpad_vertical_axis", -1))
        self._dpad_axes_enabled = self._dpad_axis_h >= 0 and self._dpad_axis_v >= 0
        self._nav_cooldown_ms = 0.0
        self._hat_cooldown_ms = 0.0
        self._stick_state: dict[int, _NavAxisState] = {}
        self._dpad_state: dict[int, _NavAxisState] = {}
        self._last_hat: tuple[int, int] | None = None
        self._raw_axis = "—"
        self._raw_button = "—"
        self._raw_hat = "—"
        self._last_normalized = "—"

    def step_cooldowns(self, dt_ms: float) -> None:
        if self._nav_cooldown_ms > 0:
            self._nav_cooldown_ms = max(0.0, self._nav_cooldown_ms - dt_ms)
        if self._hat_cooldown_ms > 0:
            self._hat_cooldown_ms = max(0.0, self._hat_cooldown_ms - dt_ms)

    def raw_debug_lines(self) -> list[str]:
        return [
            f"raw axis: {self._raw_axis}",
            f"raw button: {self._raw_button}",
            f"raw hat: {self._raw_hat}",
            f"normalized: {self._last_normalized}",
        ]

    def _note_normalized(self, action: InputAction) -> None:
        self._last_normalized = action.name

    def _start_nav_cooldown(self) -> None:
        self._nav_cooldown_ms = self._repeat_ms

    def actions_from_hat(self, event: pygame.event.Event) -> Iterator[InputAction]:
        x, y = event.value
        self._raw_hat = f"({x},{y})"
        if (x, y) == self._last_hat:
            return
        self._last_hat = (x, y)
        if self._hat_cooldown_ms > 0:
            return
        if y == 1:
            self._note_normalized(InputAction.MENU_UP)
            yield InputAction.MENU_UP
            self._hat_cooldown_ms = self._hat_repeat_ms
        elif y == -1:
            self._note_normalized(InputAction.MENU_DOWN)
            yield InputAction.MENU_DOWN
            self._hat_cooldown_ms = self._hat_repeat_ms
        elif x == -1:
            self._note_normalized(InputAction.MENU_LEFT)
            yield InputAction.MENU_LEFT
            self._hat_cooldown_ms = self._hat_repeat_ms
        elif x == 1:
            self._note_normalized(InputAction.MENU_RIGHT)
            yield InputAction.MENU_RIGHT
            self._hat_cooldown_ms = self._hat_repeat_ms

    def actions_from_button(self, button: int) -> Iterator[InputAction]:
        self._raw_button = str(button)
        if button in self._maps["menu_up_buttons"]:
            yield from self._yield_nav(InputAction.MENU_UP)
            return
        if button in self._maps["menu_down_buttons"]:
            yield from self._yield_nav(InputAction.MENU_DOWN)
            return
        if button in self._maps["menu_left_buttons"]:
            yield from self._yield_nav(InputAction.MENU_LEFT)
            return
        if button in self._maps["menu_right_buttons"]:
            yield from self._yield_nav(InputAction.MENU_RIGHT)
            return
        if button in self._maps["confirm_buttons"]:
            self._note_normalized(InputAction.CONFIRM)
            yield InputAction.CONFIRM
            return
        if button in self._maps["back_buttons"]:
            self._note_normalized(InputAction.BACK)
            yield InputAction.BACK
            return
        if self._maps["exit_buttons"] and button in self._maps["exit_buttons"]:
            self._note_normalized(InputAction.EXIT)
            yield InputAction.EXIT
            return

    def _yield_nav(self, action: InputAction) -> Iterator[InputAction]:
        if self._nav_cooldown_ms > 0:
            return
        self._note_normalized(action)
        yield action
        self._start_nav_cooldown()

    def _apply_center(self, v: float) -> float:
        if abs(v) < self._center:
            return 0.0
        return v

    def _read_axis_pair(
        self, joy: pygame.joystick.Joystick, axis_h: int, axis_v: int
    ) -> tuple[float, float] | None:
        try:
            if not joy.get_init():
                return None
            n = joy.get_numaxes()
            if axis_h >= n or axis_v >= n:
                return None
            vx = self._apply_center(float(joy.get_axis(axis_h)))
            vy = self._apply_center(float(joy.get_axis(axis_v)))
            return (vx, vy)
        except (pygame.error, AttributeError):
            return None

    def _read_stick(self, joy: pygame.joystick.Joystick) -> tuple[float, float] | None:
        return self._read_axis_pair(joy, self._left_axis_h, self._left_axis_v)

    def _read_dpad_axes(self, joy: pygame.joystick.Joystick) -> tuple[float, float] | None:
        if not self._dpad_axes_enabled:
            return None
        return self._read_axis_pair(joy, self._dpad_axis_h, self._dpad_axis_v)

    def _stick_signs(self, vx: float, vy: float) -> tuple[int, int]:
        th = self._threshold
        return _axis_sign(vx, th), _axis_sign(vy, th)

    def _emit_nav_edges(self, new_h: int, new_v: int, st: _NavAxisState) -> Iterator[InputAction]:
        """At most one MENU_* per call; vertical edges before horizontal."""
        for action in self._emit_vertical_edge(st, new_v):
            yield action
            return
        yield from self._emit_horizontal_edge(st, new_h)

    def _emit_vertical_edge(self, st: _NavAxisState, new_v: int) -> Iterator[InputAction]:
        prev = st.v
        if new_v == prev:
            return
        if new_v == 0:
            st.v = 0
            return
        if self._nav_cooldown_ms > 0:
            return
        st.v = new_v
        if new_v == -1:
            self._note_normalized(InputAction.MENU_UP)
            yield InputAction.MENU_UP
        else:
            self._note_normalized(InputAction.MENU_DOWN)
            yield InputAction.MENU_DOWN
        self._start_nav_cooldown()

    def _emit_horizontal_edge(self, st: _NavAxisState, new_h: int) -> Iterator[InputAction]:
        prev = st.h
        if new_h == prev:
            return
        if new_h == 0:
            st.h = 0
            return
        if self._nav_cooldown_ms > 0:
            return
        st.h = new_h
        if new_h == -1:
            self._note_normalized(InputAction.MENU_LEFT)
            yield InputAction.MENU_LEFT
        else:
            self._note_normalized(InputAction.MENU_RIGHT)
            yield InputAction.MENU_RIGHT
        self._start_nav_cooldown()

    def _try_stick_nav(self, iid: int, joy: pygame.joystick.Joystick) -> Iterator[InputAction]:
        pair = self._read_stick(joy)
        if pair is None:
            return
        vx, vy = pair
        nh, nv = self._stick_signs(vx, vy)
        st = self._stick_state.setdefault(iid, _NavAxisState())
        yield from self._emit_nav_edges(nh, nv, st)

    def _try_dpad_axis_nav(self, iid: int, joy: pygame.joystick.Joystick) -> Iterator[InputAction]:
        pair = self._read_dpad_axes(joy)
        if pair is None:
            return
        vx, vy = pair
        nh, nv = self._stick_signs(vx, vy)
        st = self._dpad_state.setdefault(iid, _NavAxisState())
        yield from self._emit_nav_edges(nh, nv, st)

    def sync_axes_from_motion(
        self, instance_id: int, axis: int, value: float
    ) -> Iterator[InputAction]:
        """Any axis motion: re-read stick + optional D-pad axes; same edge rules as poll."""
        self._raw_axis = f"id={instance_id} a{axis}={value:+.3f}"
        joy = self._joysticks.get(instance_id)
        if joy is None:
            return
        sp = self._read_stick(joy)
        if sp is not None:
            vx, vy = sp
            self._raw_axis = f"id={instance_id} stick vx={vx:+.2f} vy={vy:+.2f}"
        dp = self._read_dpad_axes(joy)
        if dp is not None:
            dx, dy = dp
            extra = f" dpad dx={dx:+.2f} dy={dy:+.2f}"
            if sp is None:
                self._raw_axis = f"id={instance_id}{extra}"
            else:
                self._raw_axis += extra

        for act in self._try_stick_nav(instance_id, joy):
            yield act
            return
        yield from self._try_dpad_axis_nav(instance_id, joy)

    def poll_analog_and_dpad_axes(self) -> Iterator[InputAction]:
        for iid, joy in self._joysticks.items():
            for act in self._try_stick_nav(iid, joy):
                yield act
                return
            for act in self._try_dpad_axis_nav(iid, joy):
                yield act
                return


class InputService:
    """Keyboard + joystick (+ GPIO stub). UI consumes InputAction only."""

    def __init__(
        self,
        input_cfg: dict[str, Any] | None,
        joysticks: dict[int, pygame.joystick.Joystick],
    ) -> None:
        cfg = input_cfg or {}
        self._debug = bool(cfg.get("debug", False))
        self._joystick_adapter = JoystickAdapter(cfg, joysticks)
        self._gpio = GPIOAdapter()
        self._axis_log_deadline = 0.0

    def set_debug(self, enabled: bool) -> None:
        self._debug = bool(enabled)

    def debug_enabled(self) -> bool:
        return self._debug

    def raw_input_debug_lines(self) -> list[str]:
        return self._joystick_adapter.raw_debug_lines()

    def actions_from_event(self, event: pygame.event.Event) -> Iterator[InputAction]:
        if event.type == pygame.KEYDOWN:
            yield from KeyboardAdapter.actions_from_keydown(event.key)
            return
        if event.type == pygame.JOYHATMOTION:
            yield from self._joystick_adapter.actions_from_hat(event)
            return
        if event.type == pygame.JOYBUTTONDOWN:
            yield from self._joystick_adapter.actions_from_button(event.button)
            return
        if event.type == pygame.JOYAXISMOTION:
            iid = getattr(event, "instance_id", -1)
            if isinstance(iid, int) and iid >= 0:
                yield from self._joystick_adapter.sync_axes_from_motion(
                    iid, event.axis, float(event.value)
                )
            return

    def poll_navigation(self) -> Iterator[InputAction]:
        yield from self._joystick_adapter.poll_analog_and_dpad_axes()
        yield from self._gpio.poll()

    def step_cooldowns(self, dt_ms: float) -> None:
        self._joystick_adapter.step_cooldowns(dt_ms)

    def debug_log_event(self, event: pygame.event.Event) -> None:
        if not self._debug:
            return
        et = event.type
        if et == pygame.JOYAXISMOTION:
            now = time.monotonic()
            if now < self._axis_log_deadline:
                return
            self._axis_log_deadline = now + 0.12
            print(
                f"[input] AXIS axis={event.axis} value={event.value:.4f} "
                f"instance_id={getattr(event, 'instance_id', '?')}"
            )
            return
        if et == pygame.JOYBUTTONDOWN:
            print(f"[input] BUTTON {event.button}")
        elif et == pygame.JOYHATMOTION:
            print(
                f"[input] HAT value={event.value} "
                f"instance_id={getattr(event, 'instance_id', '?')}"
            )
        elif et == pygame.JOYDEVICEADDED:
            print(f"[input] DEVICE ADDED device_index={getattr(event, 'device_index', '?')}")
        elif et == pygame.JOYDEVICEREMOVED:
            print(f"[input] DEVICE REMOVED instance_id={getattr(event, 'instance_id', '?')}")

    def intents_from_event(self, event: pygame.event.Event) -> Iterator[InputAction]:
        yield from self.actions_from_event(event)

    def poll_left_stick_navigation(self) -> Iterator[InputAction]:
        yield from self.poll_navigation()

    def step_joy_cooldown(self, dt_ms: float) -> None:
        self.step_cooldowns(dt_ms)
