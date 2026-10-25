"""Config flow for Kano Wand integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
try:
    from homeassistant.config_entries import ConfigFlowResult as FlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, SERVICE_INFO, SERVICE_IO

_LOGGER = logging.getLogger(__name__)

KANO_SERVICE_UUIDS = {SERVICE_INFO.lower(), SERVICE_IO.lower()}


def _is_kano_wand(discovery_info: BluetoothServiceInfoBleak) -> bool:
    """Return True if the discovered BLE device is a Kano Wand."""
    if discovery_info.name and discovery_info.name.startswith("Kano-Wand"):
        return True
    if discovery_info.service_uuids:
        for uuid in discovery_info.service_uuids:
            if uuid.lower() in KANO_SERVICE_UUIDS:
                return True
    return False


class KanoWandConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kano Wand."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        name = discovery_info.name or f"Kano Wand ({discovery_info.address})"
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        assert self._discovery_info is not None
        name = self._discovery_info.name or f"Kano Wand ({self._discovery_info.address})"

        if user_input is not None:
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._discovered_devices[address],
                data={
                    CONF_ADDRESS: address,
                },
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, connectable=True):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue

            if _is_kano_wand(discovery_info):
                self._discovered_devices[address] = (
                    discovery_info.name or f"Kano Wand ({address})"
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices),
                }
            ),
        )
