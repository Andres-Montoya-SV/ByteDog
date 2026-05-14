"""Terminal logging for SDL input when ``input.debug`` is enabled (throttled axis spam)."""

from __future__ import annotations

import time

import pygame


def log_pygame_input_event(*, enabled: bool, axis_log_deadline_ref: list[float], event: pygame.event.Event) -> None:
    """Mutates ``axis_log_deadline_ref[0]`` as monotonic deadline for axis log throttle."""
    if not enabled:
        return
    et = event.type
    if et == pygame.JOYAXISMOTION:
        now = time.monotonic()
        if now < axis_log_deadline_ref[0]:
            return
        axis_log_deadline_ref[0] = now + 0.12
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
