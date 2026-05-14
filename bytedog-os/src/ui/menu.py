"""Keyboard-navigable launcher menu."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class MenuAction(str, Enum):
    RETRO_GAMES = "retro_games"
    CYBERDECK = "cyberdeck"
    CHICHA = "chicha"
    TERMINAL = "terminal"
    SETTINGS = "settings"
    SHUTDOWN = "shutdown"


@dataclass(slots=True)
class MenuItem:
    label: str
    subtitle: str
    action: MenuAction


@dataclass(slots=True)
class LauncherMenu:
    """Vertical launcher list with circular wrap on up/down."""

    items: list[MenuItem] = field(
        default_factory=lambda: [
            MenuItem("Retro", "Juega tus clásicos", MenuAction.RETRO_GAMES),
            MenuItem("Cyberdeck", "Herramientas y redes", MenuAction.CYBERDECK),
            MenuItem("Chicha", "Cuida a tu compañera", MenuAction.CHICHA),
            MenuItem("Terminal", "Línea de comandos", MenuAction.TERMINAL),
            MenuItem("Ajustes", "Sistema y personalización", MenuAction.SETTINGS),
            MenuItem("Apagar", "Apagar el sistema", MenuAction.SHUTDOWN),
        ]
    )
    selected_index: int = 0
    _handlers: dict[MenuAction, Callable[[], None]] = field(
        init=False, repr=False, default_factory=dict
    )

    @property
    def selected(self) -> MenuItem:
        return self.items[self.selected_index]

    def move_up(self) -> bool:
        """Circular selection; returns False when there is only one item."""
        n = len(self.items)
        if n <= 1:
            return False
        prev = self.selected_index
        self.selected_index = (self.selected_index - 1) % n
        return self.selected_index != prev

    def move_down(self) -> bool:
        n = len(self.items)
        if n <= 1:
            return False
        prev = self.selected_index
        self.selected_index = (self.selected_index + 1) % n
        return self.selected_index != prev

    def move_left(self) -> bool:
        """Reserved for horizontal menus; vertical list ignores."""
        return False

    def move_right(self) -> bool:
        """Reserved for horizontal menus; vertical list ignores."""
        return False

    def bind_actions(self, handlers: dict[MenuAction, Callable[[], None]]) -> None:
        self._handlers = dict(handlers)

    def activate(self) -> None:
        fn = self._handlers.get(self.selected.action)
        if fn:
            fn()
