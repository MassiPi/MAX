from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from .const import DOMAIN
from .coordinator import MaxCoordinator
from socket import timeout
from pathlib import Path
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from .services import async_setup_services
import logging
_LOGGER = logging.getLogger(__name__)

CARD_VERSION = "1.0.0"
CARD_URL = f"/{DOMAIN}_static/max-schedule-card.js"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    card_path = Path(__file__).parent / "frontend" / "max-schedule-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")

    async_setup_services(hass)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    
    try:
        coordinator = MaxCoordinator(hass, entry)

    except (timeout, OSError) as err:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "cube_unavailable",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="cube_unavailable",
        )

        raise ConfigEntryNotReady(
            f"MAX! Cube non raggiungibile: {err}"
        ) from err
        
    await coordinator.async_config_entry_first_refresh()
    
    ir.async_delete_issue(hass, DOMAIN, "cube_unavailable")
    
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["binary_sensor", "climate", "sensor", "number", "select"])
    return True

async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload MAX! Cube integration."""
    
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["binary_sensor", "climate", "sensor", "number", "select"],
    )
    
    if not unload_ok:
        return False

    coordinator = hass.data[DOMAIN][entry.entry_id]

    try:
        await coordinator.async_close()
    except Exception:
        _LOGGER.exception("MAX: ERROR CLOSING CONNECTION")
        raise

    hass.data[DOMAIN].pop(entry.entry_id, None)
 
    return True
