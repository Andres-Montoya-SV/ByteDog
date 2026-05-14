"""Facade: keyboard + joystick (+ future GPIO). App code depends on this API only."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pygame

from src.services.input.actions import InputAction
from src.services.input.debug import log_pygame_input_event
from src.services.input.joystick import JoystickAdapter
from src.services.input.keyboard import KeyboardAdapter


class _GPIOAdapter:
    def poll(self) -> Iterator[InputAction]:
        yield from ()


class InputService:
    """Keyboard + joystick (+ GPIO stub). UI consumes ``InputAction`` only."""

    def __init__(
        self,
        input_cfg: dict[str, Any] | None,
        joysticks: dict[int, pygame.joystick.Joystick],
    ) -> None:
        cfg = input_cfg or {}
        self._debug = bool(cfg.get("debug", False))
        self._joystick_adapter = JoystickAdapter(cfg, joysticks)
        self._gpio = _GPIOAdapter()
        self._axis_log_deadline: list[float] = [0.0]

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
        log_pygame_input_event(
            enabled=self._debug,
            axis_log_deadline_ref=self._axis_log_deadline,
            event=event,
        )

    def intents_from_event(self, event: pygame.event.Event) -> Iterator[InputAction]:
        yield from self.actions_from_event(event)

    def poll_left_stick_navigation(self) -> Iterator[InputAction]:
        yield from self.poll_navigation()

    def step_joy_cooldown(self, dt_ms: float) -> None:
        self.step_cooldowns(dt_ms)
