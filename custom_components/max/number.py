
"""MAX! Cube configuration numbers (coordinator-based)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class MaxNumberDescription(NumberEntityDescription):
    """MAX! configuration number description."""

    device_attr: str
    min_value: float
    max_value: float
    step: float


# Configuration shared by radiator and wall thermostats.
COMMON_TEMP_NUMBERS = (
    MaxNumberDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        #name="Comfort Temperature",
        device_attr="comfort_temperature",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer",
        min_value=4.5,
        max_value=30.5,
        step=0.5,
    ),
    MaxNumberDescription(
        key="eco_temperature",
        translation_key="eco_temperature",
        #name="Eco Temperature",
        device_attr="eco_temperature",
        native_unit_of_measurement="°C",
        icon="mdi:leaf",
        min_value=4.5,
        max_value=30.5,
        step=0.5,
    ),
    MaxNumberDescription(
        key="max_temperature",
        translation_key="max_temperature",
        #name="Max Temperature",
        device_attr="max_temperature",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer-high",
        min_value=4.5,
        max_value=30.5,
        step=0.5,
    ),
    MaxNumberDescription(
        key="min_temperature",
        translation_key="min_temperature",
        #name="Min Temperature",
        device_attr="min_temperature",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer-low",
        min_value=4.5,
        max_value=30.5,
        step=0.5,
    ),
)


# Configuration exclusive to radiator thermostats.
RADIATOR_TEMP_NUMBERS = (
    MaxNumberDescription(
        key="temperature_offset",
        translation_key="temperature_offset",
        #name="Temperature Offset",
        device_attr="temperature_offset",
        native_unit_of_measurement="°C",
        icon="mdi:thermometer-lines",
        min_value=-3.5,
        max_value=3.5,
        step=0.5,
    ),
    MaxNumberDescription(
        key="window_open_duration",
        translation_key="window_open_duration",
        #name="Window Open Duration",
        device_attr="window_open_duration",
        native_unit_of_measurement="min",
        icon="mdi:timer-outline",
        min_value=0,
        max_value=60,
        step=5,
    ),
    MaxNumberDescription(
        key="window_open_temp",
        translation_key="temperature_window_open",
        #name="Window Open Temperature",
        device_attr="temperature_window_open",
        native_unit_of_measurement="°C",
        icon="mdi:window-open-variant",
        min_value=4.5,
        max_value=30.5,
        step=0.5,
    ),
)

RADIATOR_VALVE_NUMBERS = (
    MaxNumberDescription(
        key="boost_value",
        translation_key="boost_value",
        #name="Boost Valve Position",
        device_attr="boost_value",
        native_unit_of_measurement="%",
        icon="mdi:valve-open",
        min_value=0,
        max_value=100,
        step=5,
    ),
    MaxNumberDescription(
        key="max_valve",
        translation_key="max_valve",
        #name="Maximum Valve Position",
        device_attr="max_valve",
        native_unit_of_measurement="%",
        icon="mdi:valve",
        min_value=0,
        max_value=100,
        step=1,
    ),
    MaxNumberDescription(
        key="valve_offset",
        translation_key="valve_offset",
        #name="Valve Offset",
        device_attr="valve_offset",
        native_unit_of_measurement="%",
        icon="mdi:tune-vertical",
        min_value=0,
        max_value=100,
        step=1,
    ),
)

class MaxCubeNumber(CoordinatorEntity, NumberEntity):
    """MAX! configuration number."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator,
        device,
        cube_device_id,
        description,
    ):
        super().__init__(coordinator)

        self.coordinator = coordinator
        self._device = device
        self.entity_description = description

        self._attr_unique_id = (
            f"{self._device.serial}_{description.key}"
        )

        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            serial_number=self._device.serial,
            name=f"{self._device.name}",
            manufacturer="eQ-3",
            model=(
                "MAX! Radiator Thermostat"
                if device.is_thermostat()
                else "MAX! Wall Thermostat"
            ),
            via_device_id=cube_device_id,
        )

    @property
    def native_value(self):
        """Return current configuration value."""

        return getattr(
            self._device,
            self.entity_description.device_attr,
            None,
        )

    async def async_set_native_value(self, value: float):
        """Write configuration to MAX! Cube."""

        device = self._device
        attr = self.entity_description.device_attr

        if device.is_wallthermostat():
            values = {
                "comfortTemp": device.comfort_temperature,
                "ecoTemp": device.eco_temperature,
                "maxTemp": device.max_temperature,
                "minTemp": device.min_temperature,
            }

            # Override the value being changed.
            values[{
                "comfort_temperature": "comfortTemp",
                "eco_temperature": "ecoTemp",
                "max_temperature": "maxTemp",
                "min_temperature": "minTemp",
            }[attr]] = value

            self.hass.create_task(
                self.coordinator.async_set_temp_config(
                    device,
                    **values,
                )
            )

        elif device.is_thermostat():
        
            # Radiator temp configuration.
            if attr in {description.device_attr for description in RADIATOR_TEMP_NUMBERS + COMMON_TEMP_NUMBERS}:
                values = {
                    "comfortTemp": device.comfort_temperature,
                    "ecoTemp": device.eco_temperature,
                    "maxTemp": device.max_temperature,
                    "minTemp": device.min_temperature,
                    "offsetTemp": device.temperature_offset,
                    "windowTemp": device.temperature_window_open,
                    "windowDuration": device.window_open_duration,
                }

                values[{
                    "comfort_temperature": "comfortTemp",
                    "eco_temperature": "ecoTemp",
                    "max_temperature": "maxTemp",
                    "min_temperature": "minTemp",
                    "temperature_offset": "offsetTemp",
                    "temperature_window_open": "windowTemp",
                    "window_open_duration": "windowDuration",
                }[attr]] = value

                self.hass.create_task(
                    self.coordinator.async_set_temp_config(
                        device,
                        **values,
                    )
                )

            # Radiator temp configuration.
            elif attr in {description.device_attr for description in RADIATOR_VALVE_NUMBERS}:
                values = {
                    "boostValve": device.boost_value,
                    "boostDuration": device.boost_duration,
                    "maxValve": device.max_valve,
                    "valveOffset": device.valve_offset,
                    "decalcDay": device.decalc_day,
                    "decalcTime": device.decalc_time,
                }

                values[{
                    "boost_value": "boostValve",
                    "boost_duration": "boostDuration",
                    "max_valve": "maxValve",
                    "valve_offset": "valveOffset",
                    "decalc_day": "decalcDay",
                    "decalc_time": "decalcTime",
                }[attr]] = value

                self.hass.create_task(
                    self.coordinator.async_set_valve_config(
                        device,
                        **values,
                    )
                )

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MAX! configuration numbers."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    cube_device_id = dr.async_get_device_id_by_identifier(
        hass,
        (DOMAIN, coordinator.data["cube"].serial),
        config_entry_id=entry.entry_id,
    )

    entities = []

    for device in coordinator.data["devices"]:

        # Radiator thermostat.
        if device.is_thermostat():
            descriptions = COMMON_TEMP_NUMBERS + RADIATOR_TEMP_NUMBERS + RADIATOR_VALVE_NUMBERS

        # Wall thermostat.
        elif device.is_wallthermostat():
            descriptions = COMMON_TEMP_NUMBERS

        # All other device types are ignored.
        else:
            continue

        entities.extend(
            MaxCubeNumber(
                coordinator,
                device,
                cube_device_id,
                description,
            )
            for description in descriptions
        )

    async_add_entities(entities)
