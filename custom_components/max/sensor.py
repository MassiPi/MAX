"""MAX! Cube sensors (coordinator-based)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor entities."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    cube_device_id = dr.async_get_device_id_by_identifier(
        hass,
        (DOMAIN, coordinator.cube.serial),
        config_entry_id=entry.entry_id,
    )
    
    entities = []

    entities.append(MaxCubeSensorDuty(coordinator, coordinator.data["cube"], cube_device_id))
    entities.append(MaxCubeSensorMemory(coordinator, coordinator.data["cube"], cube_device_id))
    entities.append(MaxCubeRFAddressSensor(coordinator, coordinator.data["cube"], cube_device_id))

    for device in coordinator.data["devices"]:
        entities.append(MaxRoomSensor(coordinator, device, cube_device_id))
        entities.append(MaxRFAddressSensor(coordinator, device, cube_device_id))
        if device.is_thermostat():
            entities.append(MaxValveSensor(coordinator, device, cube_device_id))
            
    async_add_entities(entities)

class MaxSensorBase(CoordinatorEntity, SensorEntity):
    """Base sensor using coordinator."""

    def __init__(self, coordinator, device, cube_device_id):
        """Initialize sensor."""

        super().__init__(coordinator)

        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            serial_number=self._device.serial,
            name=f"{self._device.name}",
            manufacturer="eQ-3",
            model="MAX! Radiator Thermostat",
            via_device_id=cube_device_id
        )
        
class MaxValveSensor(MaxSensorBase):
    """Valve aperture sensor."""
    _attr_icon = "mdi:valve"
    #_attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "valve"
        #self._attr_name = f"valve"
        self._attr_unique_id = f"{self._device.serial}_valve"

    @property
    def native_value(self):
        """Return valve position."""
        return self._device.valve_position
        
        
class MaxCubeSensorBase(CoordinatorEntity, SensorEntity):
    """Base sensor using coordinator."""

    def __init__(self, coordinator, device, cube_device_id):
        """Initialize sensor."""

        super().__init__(coordinator)

        self._device = device
        
        # Device Info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.serial)},
            serial_number=self._device.serial,
            name=f"{self._device.name}",
            manufacturer="eQ-3",
            model="MAX! Cube",
        )
        
class MaxCubeSensorDuty(MaxCubeSensorBase):
    """Duty Cycle sensor."""
    _attr_icon = "mdi:chart-line"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "duty_cycle"
        #self._attr_name = f"Duty Cycle"
        self._attr_unique_id = f"{self._device.serial}_duty_cycle"

    @property
    def native_value(self):
        """Return valve position."""
        return self._device.duty
        
class MaxCubeSensorMemory(MaxCubeSensorBase):
    """Free memory slots sensor."""
    _attr_icon = "mdi:memory"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "slots"
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "free_memory_slots"
        #self._attr_name = f"Free Memory Slots"
        self._attr_unique_id = f"{self._device.serial}_free_memory_slots"

    @property
    def native_value(self):
        """Return memory."""
        value = self._device.memory
        return int(value) if value is not None else None

class MaxRoomSensor(MaxSensorBase):
    """Room number sensor."""

    _attr_icon = "mdi:door"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "room"
        #self._attr_name = "Room"
        self._attr_unique_id = f"{self._device.serial}_room"

    @property
    def native_value(self):
        return self._device.room_id


class MaxRFAddressSensor(MaxSensorBase):
    """RF address sensor."""

    _attr_icon = "mdi:identifier"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "rf_address"
        #self._attr_name = "RF Address"
        self._attr_unique_id = f"{self._device.serial}_rf_address"

    @property
    def native_value(self):
        return self._device.rf_address

class MaxCubeRFAddressSensor(MaxCubeSensorBase):
    """RF address sensor."""

    _attr_icon = "mdi:identifier"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        self._attr_translation_key = "rf_address"
        #self._attr_name = "RF Address"
        self._attr_unique_id = f"{self._device.serial}_rf_address"

    @property
    def native_value(self):
        return self._device.rf_address