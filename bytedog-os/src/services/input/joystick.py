"""SDL2 joystick: hats, mapped face buttons, analog + optional D-pad axes (PS4-friendly)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pygame

from src.services.input.actions import InputAction
from src.services.input.state import NavAxisState, axis_sign, mapping_sets


class JoystickAdapter:
    """
    Axis deflection uses threshold T (config ``deadzone``).
    ``stick_center_deadzone`` snaps near-zero raw values before T.

    Edge detection per ``instance_id``; cooldown limits repeat without stuck loops.
    """

    def __init__(self, cfg: dict[str, Any], joysticks: dict[int, pygame.joystick.Joystick]) -> None:
        self._joysticks = joysticks
        self._maps = mapping_sets(cfg)
        self._threshold = float(cfg.get("deadzone", 0.55))
        self._center = float(cfg.get("stick_center_deadzone", 0.12))
        self._repeat_ms = float(cfg.get("repeat_cooldown_ms", 180.0))
        self._repeat_min_ms = float(cfg.get("repeat_cooldown_min_ms", 92.0))
        self._repeat_accel_step_ms = float(cfg.get("repeat_accel_step_ms", 16.0))
        self._hat_repeat_ms = float(cfg.get("hat_repeat_ms", self._repeat_ms))
        self._left_axis_h = int(cfg.get("left_stick_horizontal_axis", 0))
        self._left_axis_v = int(cfg.get("left_stick_vertical_axis", 1))
        self._dpad_axis_h = int(cfg.get("dpad_horizontal_axis", -1))
        self._dpad_axis_v = int(cfg.get("dpad_vertical_axis", -1))
        self._dpad_axes_enabled = self._dpad_axis_h >= 0 and self._dpad_axis_v >= 0
        self._nav_cooldown_ms = 0.0
        self._hat_cooldown_ms = 0.0
        self._stick_state: dict[int, NavAxisState] = {}
        self._dpad_state: dict[int, NavAxisState] = {}
        self._last_hat: tuple[int, int] | None = None
        self._raw_axis = "—"
        self._raw_button = "—"
        self._raw_hat = "—"
        self._last_normalized = "—"
        self._smooth_alpha = float(cfg.get("stick_smooth_alpha", 0.0))
        self._smooth_store: dict[tuple[int, int], float] = {}
        self._burst_nav_count = 0
        self._burst_decay_ms = 0.0

    def step_cooldowns(self, dt_ms: float) -> None:
        if self._nav_cooldown_ms > 0:
            self._nav_cooldown_ms = max(0.0, self._nav_cooldown_ms - dt_ms)
        if self._hat_cooldown_ms > 0:
            self._hat_cooldown_ms = max(0.0, self._hat_cooldown_ms - dt_ms)
        if self._burst_decay_ms > 0:
            self._burst_decay_ms = max(0.0, self._burst_decay_ms - dt_ms)
            if self._burst_decay_ms <= 0.0:
                self._burst_nav_count = 0

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
        self._nav_cooldown_ms = self._effective_repeat_ms()
        self._burst_nav_count = min(24, self._burst_nav_count + 1)
        self._burst_decay_ms = 420.0

    def _effective_repeat_ms(self) -> float:
        if self._burst_nav_count < 2:
            return self._repeat_ms
        extra = (self._burst_nav_count - 1) * self._repeat_accel_step_ms
        return max(self._repeat_min_ms, self._repeat_ms - extra)

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

    def _smooth_axis(self, joy_id: int, axis_index: int, raw: float) -> float:
        if self._smooth_alpha <= 0.001:
            return raw
        key = (joy_id, axis_index)
        prev = self._smooth_store.get(key, raw)
        a = max(0.02, min(0.55, self._smooth_alpha))
        blended = prev + a * (raw - prev)
        self._smooth_store[key] = blended
        return blended

    def _read_axis_pair(
        self, joy: pygame.joystick.Joystick, axis_h: int, axis_v: int
    ) -> tuple[float, float] | None:
        try:
            if not joy.get_init():
                return None
            n = joy.get_numaxes()
            if axis_h >= n or axis_v >= n:
                return None
            iid = 0
            try:
                iid = int(joy.get_instance_id())
            except (pygame.error, AttributeError, TypeError):
                pass
            vx = self._apply_center(self._smooth_axis(iid, axis_h, float(joy.get_axis(axis_h))))
            vy = self._apply_center(self._smooth_axis(iid, axis_v, float(joy.get_axis(axis_v))))
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
        return axis_sign(vx, th), axis_sign(vy, th)

    def _emit_nav_edges(self, new_h: int, new_v: int, st: NavAxisState) -> Iterator[InputAction]:
        for action in self._emit_vertical_edge(st, new_v):
            yield action
            return
        yield from self._emit_horizontal_edge(st, new_h)

    def _emit_vertical_edge(self, st: NavAxisState, new_v: int) -> Iterator[InputAction]:
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

    def _emit_horizontal_edge(self, st: NavAxisState, new_h: int) -> Iterator[InputAction]:
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
        st = self._stick_state.setdefault(iid, NavAxisState())
        yield from self._emit_nav_edges(nh, nv, st)

    def _try_dpad_axis_nav(self, iid: int, joy: pygame.joystick.Joystick) -> Iterator[InputAction]:
        pair = self._read_dpad_axes(joy)
        if pair is None:
            return
        vx, vy = pair
        nh, nv = self._stick_signs(vx, vy)
        st = self._dpad_state.setdefault(iid, NavAxisState())
        yield from self._emit_nav_edges(nh, nv, st)

    def sync_axes_from_motion(
        self, instance_id: int, axis: int, value: float
    ) -> Iterator[InputAction]:
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
