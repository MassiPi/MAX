"""MaxCube coordinator."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import issue_registry as ir

from socket import timeout
from threading import Lock
import time
import asyncio

from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
)

from .maxcube.cube import MaxCube
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

class MaxCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30)
        )
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        self.mutex = Lock()

        self.cube = MaxCube(self.host, self.port, now=now)
        self.cube.use_persistent_connection = True
        
    async def _async_update_data(self):
        """Fetch data from MaxCube."""
        try:
            data = await self.hass.async_add_executor_job(
                self._safe_update
            )

            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                "cube_unavailable",
            )

            return data

        except (timeout, OSError) as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "cube_unavailable",
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="cube_unavailable",
            )

            raise UpdateFailed(
                f"MaxCube connection failed: {err}"
            ) from err        

    def _safe_update(self):
        """Blocking update wrapped for executor."""
        with self.mutex:
            self.cube.update()

        devices_by_room = {}

        for d in self.cube.devices:
            devices_by_room.setdefault(d.room_id, []).append(d)

        self._build_window_open_fix(devices_by_room)
        self._update_cube_derived_state()
        return {
            "cube": self.cube,
            "devices": self.cube.devices,
            "rooms_by_id": {r.id: r for r in self.cube.rooms},
            "devices_by_room": devices_by_room
        }
        
    async def async_close(self):
        await self.hass.async_add_executor_job(self.cube.disconnect)        

    async def async_set_temperature(self, device, temp, mode):
        """Write + forced refresh for MAX cube latency."""
        def _write():
            with self.mutex:
                try:
                    self.cube.set_temperature_mode(device, temp, mode)
                except (timeout, OSError):
                    _LOGGER.error("Setting HVAC mode failed")

        await self.hass.async_add_executor_job(_write)
        await asyncio.sleep(2)
        await self.async_request_refresh()
        #await self._async_update_data()

    def set_temperature(self, device, temp, mode):
        self.hass.async_create_task(
            self.async_set_temperature(device, temp, mode)
        )

    async def async_set_temp_config(self, device,  comfortTemp, ecoTemp, maxTemp, minTemp, offsetTemp=0, windowTemp=0, windowDuration=0):
        """Write + forced refresh for MAX cube latency."""
        def _write():
            with self.mutex:
                try:
                    self.cube.set_temp_config(device, comfortTemp, ecoTemp, maxTemp, minTemp, offsetTemp, windowTemp, windowDuration)
                except (timeout, OSError):
                    _LOGGER.error("Setting temp config failed")

        def _update():
            with self.mutex:
                try:
                    self.cube.update_config(device.rf_address)
                except (timeout, OSError):
                    _LOGGER.error("Update temp config failed")

        await self.hass.async_add_executor_job(_write)
        await asyncio.sleep(2)
        await self.hass.async_add_executor_job(_update)
        await asyncio.sleep(2)
        await self.async_request_refresh()

    def set_temp_config(self, device, comfortTemp, ecoTemp, maxTemp, minTemp, offsetTemp, windowTemp, windowDuration):
        self.hass.async_create_task(
            self.async_set_temp_config(device, comfortTemp, ecoTemp, maxTemp, minTemp, offsetTemp, windowTemp, windowDuration)
        )
                    
    async def async_set_valve_config(self, device,  boostValve, boostDuration, maxValve, valveOffset, decalcDay, decalcTime):
        """Write + forced refresh for MAX cube latency."""
        def _write():
            with self.mutex:
                try:
                    self.cube.set_valve_config(device,  boostValve, boostDuration, maxValve, valveOffset, decalcDay, decalcTime)
                except (timeout, OSError):
                    _LOGGER.error("Setting valve config failed")

        def _update():
            with self.mutex:
                try:
                    self.cube.update_config(device.rf_address)
                except (timeout, OSError):
                    _LOGGER.error("Update valve config failed")

        await self.hass.async_add_executor_job(_write)
        await asyncio.sleep(2)
        await self.hass.async_add_executor_job(_update)
        await asyncio.sleep(2)
        await self.async_request_refresh()

    def set_valve_config(self, device,  boostValve, boostDuration, maxValve, valveOffset, decalcDay, decalcTime):
        self.hass.async_create_task(
            self.async_set_valve_config(device,  boostValve, boostDuration, maxValve, valveOffset, decalcDay, decalcTime)
        )


    def _build_window_open_fix(self, devices_by_room):
        """Fix wall thermostat missing window_open value."""
        for room_id, devices in devices_by_room.items():
            thermostat_value = None

            for dev in devices:
                if dev.is_thermostat() and getattr(dev, "temperature_window_open", 0) > 0:
                    thermostat_value = dev.temperature_window_open
                    break

            if thermostat_value is None:
                continue

            for dev in devices:
                if dev.is_wallthermostat():
                    dev.temperature_window_open = thermostat_value

    def _update_cube_derived_state(self):
        """Mutate cube derived attributes after refresh."""
        cube = self.cube

        eco = 0.0
        comfort = 0.0
        window_open = 0.0

        for dev in cube.devices:
            if dev.is_thermostat() or dev.is_wallthermostat():
                eco = max(eco, getattr(dev, "eco_temperature", 0.0))
                comfort = max(comfort, getattr(dev, "comfort_temperature", 0.0))
                window_open = max(window_open, getattr(dev, "temperature_window_open", 0.0))

        cube.eco_temperature = eco
        cube.comfort_temperature = comfort
        cube.temperature_window_open = window_open