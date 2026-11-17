"""MAX! Cube binary sensors (coordinator-based)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Setup binary sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    cube_device_id = dr.async_get_device_id_by_identifier(
        hass,
        (DOMAIN, coordinator.cube.serial),
        config_entry_id=entry.entry_id,
    )
    
    entities = []

    for device in coordinator.data["devices"]:
        entities.append(MaxCubeBattery(coordinator, device, cube_device_id))
        entities.append(MaxCubeLink(coordinator, device, cube_device_id))
        #entities.append(MaxCubeBattery(coordinator, device))
        #entities.append(MaxCubeLink(coordinator, device))

        if device.is_windowshutter():
            entities.append(MaxCubeShutter(coordinator, device, cube_device_id))
            #entities.append(MaxCubeShutter(coordinator, device))

    async_add_entities(entities)

class MaxCubeBinaryBase(CoordinatorEntity, BinarySensorEntity):
    """Base binary sensor using coordinator."""

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator)

        self._device = device
        self._room = self.coordinator.data["rooms_by_id"][device.room_id]
        
        model = None

        if device.is_windowshutter():
            model = "MAX! Window Contact"
        elif device.is_thermostat():
            model = "MAX! Radiator Thermostat"
        elif device.is_wallthermostat():
            model = "MAX! Wall Thermostat"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            serial_number=self._device.serial,
            name=f"{device.name}",
            manufacturer="eQ-3",
            model=model,
            via_device_id=cube_device_id,
            #via_device=(DOMAIN, self.coordinator.cube.serial),
        )
        
class MaxCubeShutter(MaxCubeBinaryBase):
    """Window shutter sensor."""

    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        #self._attr_name = f"{device.name}"
        self._attr_has_entity_name = True
        self._attr_translation_key = "shutter"
        #self._attr_name = f"shutter"  
        self._attr_unique_id = f"{device.serial}_shutter"

    @property
    def is_on(self):
        return self._device.is_open
        
class MaxCubeBattery(MaxCubeBinaryBase):
    """Battery sensor."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        #self._attr_name = f"{device.name} battery"
        self._attr_has_entity_name = True
        self._attr_translation_key = "battery"
        #self._attr_name = f"battery"  
        self._attr_unique_id = f"{device.serial}_battery"

    @property
    def is_on(self):
        return self._device.battery == 1
        
class MaxCubeLink(MaxCubeBinaryBase):
    """Link error sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator, device, cube_device_id):
        super().__init__(coordinator, device, cube_device_id)

        #self._attr_name = f"{device.name} link error"
        self._attr_has_entity_name = True
        self._attr_translation_key = "link_error"
        #self._attr_name = f"link error"  
        self._attr_unique_id = f"{device.serial}_link_error"

    @property
    def is_on(self):
        return self._device.link_error == 1