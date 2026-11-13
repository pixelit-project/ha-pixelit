"""Direct PixelIt display control over the existing WebSocket."""

from __future__ import annotations

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.exceptions import ServiceValidationError

from .content import build_screen
from .entity import device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Add display control and its targeted message action."""
    async_add_entities([PixelItLight(entry)])


class PixelItLight(LightEntity):
    """Represent display power and brightness with firmware state feedback."""

    _attr_has_entity_name = True
    _attr_translation_key = "display"
    _attr_icon = "mdi:led-strip-variant"
    _attr_should_poll = False
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, entry) -> None:
        self._coordinator = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_display"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self._coordinator.add_control_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        info = self._coordinator.info
        return self._coordinator.connected and isinstance(info.get("sleepMode"), bool)

    @property
    def is_on(self) -> bool | None:
        sleep = self._coordinator.info.get("sleepMode")
        return not sleep if isinstance(sleep, bool) else None

    @property
    def brightness(self) -> int | None:
        value = self._coordinator.info.get("currentMatrixBrightness")
        return value if type(value) is int and 0 <= value <= 255 else None

    async def async_turn_on(self, **kwargs) -> None:
        screen = {"sleepMode": False}
        if ATTR_BRIGHTNESS in kwargs:
            screen["brightness"] = kwargs[ATTR_BRIGHTNESS]
        await self._coordinator.player.async_power(screen)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.player.async_power({"sleepMode": True})

    async def async_show_message(
        self,
        message: str,
        color: str,
        scroll: str,
        large_font: bool,
        center: bool,
        protection_duration: float,
        icon: int | None = None,
        icon_animation_delay: int = 100,
    ) -> None:
        """Wake separately: firmware ignores content alongside sleepMode."""
        screen = build_screen(
            message=message,
            color=color,
            scroll=scroll,
            large_font=large_font,
            center=center,
            icon=icon,
        )
        await self._coordinator.player.async_show_message(
            self._with_icon(screen, icon, icon_animation_delay),
            protection_duration,
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Expose playback status without recording full screen payloads."""
        player = self._coordinator.player
        return {
            "current_screen": player.current,
            "playlist": list(player.playlist),
            "stored_screens": list(player.screens),
            "alert_active": player.alert_active,
            "playback_error": player.last_error,
        }

    async def async_set_screen(
        self,
        name: str,
        screen: dict | None = None,
        duration: float = 5,
        icon: int | None = None,
        icon_animation_delay: int = 100,
        message: str | None = None,
        clock: bool = False,
        color: str = "#FFFFFF",
        scroll: str = "auto",
        large_font: bool = False,
        center: bool = True,
    ) -> None:
        screen = build_screen(
            screen=screen,
            message=message,
            clock=clock,
            color=color,
            scroll=scroll,
            large_font=large_font,
            center=center,
            icon=icon,
        )
        await self._coordinator.player.async_set_screen(
            name, self._with_icon(screen, icon, icon_animation_delay), duration
        )

    async def async_show_screen(self, name: str) -> None:
        await self._coordinator.player.async_show_screen(name)

    async def async_set_playlist(self, screens: list[str]) -> None:
        await self._coordinator.player.async_set_playlist(screens)

    async def async_stop_playlist(self) -> None:
        await self._coordinator.player.async_stop_playlist()

    async def async_show_alert(
        self,
        screen: dict | None = None,
        duration: float = 10,
        icon: int | None = None,
        icon_animation_delay: int = 100,
        message: str | None = None,
        clock: bool = False,
        color: str = "#FFFFFF",
        scroll: str = "auto",
        large_font: bool = False,
        center: bool = True,
    ) -> None:
        screen = build_screen(
            screen=screen,
            message=message,
            clock=clock,
            color=color,
            scroll=scroll,
            large_font=large_font,
            center=center,
            icon=icon,
        )
        await self._coordinator.player.async_show_alert(
            self._with_icon(screen, icon, icon_animation_delay), duration
        )

    @staticmethod
    def _with_icon(screen: dict, icon: int | None, delay: int) -> dict:
        if icon is None:
            return screen
        if "icon" in screen:
            raise ServiceValidationError(
                "Specify icon on the action or inside screen, not both"
            )
        return {**screen, "icon": icon, "icon_animation_delay": delay}
