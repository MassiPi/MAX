"""MAX! Cube configuration selects (coordinator-based)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


BOOST_DURATIONS = [
    "0",
    "5",
    "10",
    "15",
    "20",
    "25",
    "30",
    "60",
]

DECALC_DAYS = [
    "saturday",
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
]

DECALC_DAY_MAPPING = {
    "sat": "saturday",
    "saturday": "saturday",
    "sun": "sunday",
    "sunday": "sunday",
    "mon": "monday",
    "monday": "monday",
    "tue": "tuesday",
    "tuesday": "tuesday",
    "wed": "wednesday",
    "wednesday": "wednesday",
    "thu": "thursday",
    "thursday": "thursday",
    "fri": "friday",
    "friday": "friday",
}

# MAX! protocol: 0 = Saturday, 1 = Sunday, ..., 6 = Friday.
DECALC_DAY_BY_PROTOCOL = {
    0: "saturday",
    1: "sunday",
    2: "monday",
    3: "tuesday",
    4: "wednesday",
    5: "thursday",
    6: "friday",
}

DECALC_HOURS = [
    f"{hour:02d}:00"
    for hour in range(24)
]


class MaxCubeSelect(CoordinatorEntity, SelectEntity):
    """Base MAX! configuration select."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator,
        device,
        cube_device_id,
        key,
        translation_key,
        #name,
        icon,
        options,
        device_attr,
    ):
        """Initialize MAX! configuration select."""

        super().__init__(coordinator)

        self._device = device
        self._key = key
        self._device_attr = device_attr

        self.entity_description = SelectEntityDescription(
            key=key,
            translation_key=translation_key,
            #name=name,
            icon=icon,
            options=options,
        )

        self._attr_unique_id = f"{device.serial}_{key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            serial_number=device.serial,
            name=device.name,
            manufacturer="eQ-3",
            model="MAX! Radiator Thermostat",
            via_device_id=cube_device_id,
        )

    @property
    def current_option(self):
        """Return current configuration option."""

        value = getattr(self._device, self._key, None)

        if value is None:
            return None

        # Boost duration: protocol values are minutes.
        if self._key == "boost_duration":
            try:
                option = str(int(value))
                return (
                    option
                    if option in BOOST_DURATIONS
                    else None
                )
            except (ValueError, TypeError):
                return None

        # Decalcification weekday.
        if self._key == "decalc_day":
            if isinstance(value, int):
                return DECALC_DAY_BY_PROTOCOL.get(value)

            normalized = str(value).strip().lower()
            return DECALC_DAY_MAPPING.get(normalized)

        # Decalcification hour.
        if self._key == "decalc_time":
            if isinstance(value, time):
                hour = value.hour

            elif isinstance(value, int):
                hour = value

            else:
                try:
                    hour = int(
                        str(value).strip().split(":")[0]
                    )
                except (ValueError, TypeError, IndexError):
                    return None

            if 0 <= hour <= 23:
                return f"{hour:02d}:00"

            return None

        return None

    async def async_select_option(self, option: str):
        """Write configuration to MAX! Cube."""

        device = self._device

        values = {
            "boostValve": device.boost_value,
            "boostDuration": device.boost_duration,
            "maxValve": device.max_valve,
            "valveOffset": device.valve_offset,
            "decalcDay": device.decalc_day,
            "decalcTime": device.decalc_time,
        }

        # Convert Home Assistant options to MAX! protocol values.
        if self._key == "boost_duration":
            option = int(option)

        elif self._key == "decalc_day":
            option = DECALC_DAYS.index(option)

        elif self._key == "decalc_time":
            option = int(option.split(":")[0])

        values[self._device_attr] = option
        
        values[self._device_attr] = option

        await self.coordinator.async_set_valve_config(
            device,
            **values,
        )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MAX! configuration selects."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    cube_device_id = dr.async_get_device_id_by_identifier(
        hass,
        (DOMAIN, coordinator.data["cube"].serial),
        config_entry_id=entry.entry_id,
    )

    entities = []

    for device in coordinator.data["devices"]:

        # These settings are available only on radiator thermostats.
        if not device.is_thermostat():
            continue

        entities.extend(
            [
                MaxCubeSelect(
                    coordinator,
                    device,
                    cube_device_id,
                    key="boost_duration",
                    translation_key="boost_duration",
                    #name="Boost Duration",
                    icon="mdi:timer-outline",
                    options=BOOST_DURATIONS,
                    device_attr="boostDuration",
                ),
                MaxCubeSelect(
                    coordinator,
                    device,
                    cube_device_id,
                    key="decalc_day",
                    translation_key="decalc_day",
                    #name="Decalcification Day",
                    icon="mdi:calendar",
                    options=DECALC_DAYS,
                    device_attr="decalcDay",
                ),
                MaxCubeSelect(
                    coordinator,
                    device,
                    cube_device_id,
                    key="decalc_time",
                    translation_key="decalc_time",
                    #name="Decalcification Hour",
                    icon="mdi:clock-outline",
                    options=DECALC_HOURS,
                    device_attr="decalcTime",
                ),
            ]
        )

    async_add_entities(entities)