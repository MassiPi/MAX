"""Azioni per leggere e scrivere il programma settimanale dei termostati MAX!."""
from __future__ import annotations

import logging
import re
import time

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_SLOTS = 7            # set_programme lavora con 7 fasce al giorno
MIN_TEMP, MAX_TEMP = 5.0, 30.0
DAY_DELAY = 1.0          # pausa (s) tra un giorno e l'altro, per non martellare la radio del Cube
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$|^24:00$")

SLOT = vol.Schema({vol.Required("until"): cv.string, vol.Required("temp"): vol.Coerce(float)})
GET_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})
SET_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("program"): vol.Schema({vol.Required(d): [SLOT] for d in DAYS}),
    }
)


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _resolve(hass: HomeAssistant, entity_id: str):
    """Da entity_id a (coordinator, dispositivo del Cube)."""
    ent = er.async_get(hass).async_get(entity_id)
    if ent is None or ent.platform != DOMAIN or ent.config_entry_id is None:
        raise ServiceValidationError(f"{entity_id} non appartiene all'integrazione {DOMAIN}")
    entry = hass.config_entries.async_get_entry(ent.config_entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("Integrazione non caricata")

    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        raise HomeAssistantError("Coordinator non trovato")

    devices = (coordinator.data or {}).get("devices", [])
    device = next((d for d in devices if d.serial == ent.unique_id), None)
    if device is None:
        raise ServiceValidationError(
            f"Nessun dispositivo del Cube con serial '{ent.unique_id}'"
        )
    if not getattr(device, "programme", None):
        raise ServiceValidationError(f"{entity_id}: il dispositivo non ha un programma settimanale")
    return coordinator, device


def _day_keys(device) -> dict[str, str]:
    """Mappa mon..sun -> chiave usata dal tuo cube.py in device.programme."""
    keymap = {str(k)[:3].lower(): k for k in device.programme}
    missing = [d for d in DAYS if d not in keymap]
    if missing:
        raise HomeAssistantError(
            f"Chiavi dei giorni non riconosciute in programme: {list(device.programme)}"
        )
    return keymap


def _normalize(program: dict) -> dict:
    """Valida e porta il programma nel formato che si aspetta set_programme."""
    out = {}
    for day in DAYS:
        slots = program[day]
        if not 1 <= len(slots) <= MAX_SLOTS:
            raise ServiceValidationError(f"{day}: servono da 1 a {MAX_SLOTS} fasce")
        prev = -1
        clean = []
        for s in slots:
            until, temp = s["until"], float(s["temp"])
            if not TIME_RE.match(until):
                raise ServiceValidationError(f"{day}: orario non valido '{until}'")
            mins = _minutes(until)
            if mins % 5:
                raise ServiceValidationError(f"{day}: gli orari devono essere multipli di 5 minuti")
            if mins <= prev:
                raise ServiceValidationError(f"{day}: gli orari devono essere crescenti")
            if not MIN_TEMP <= temp <= MAX_TEMP or (temp * 2) % 1:
                raise ServiceValidationError(
                    f"{day}: temperatura {temp} non valida ({MIN_TEMP}-{MAX_TEMP}, passi da 0,5)"
                )
            prev = mins
            clean.append({"temp": temp, "until": until})
        if clean[-1]["until"] != "24:00":
            raise ServiceValidationError(f"{day}: l'ultima fascia deve finire alle 24:00")
        out[day] = clean
    return out


def _read(device) -> dict:
    """Legge il programma dallo stato già in memoria (nessun traffico verso il Cube)."""
    keymap = _day_keys(device)
    return {
        day: [
            {"until": s["until"], "temp": float(s["temp"])}
            for s in device.programme[keymap[day]]
        ]
        for day in DAYS
    }


async def _get_program(call: ServiceCall) -> dict:
    _, device = _resolve(call.hass, call.data["entity_id"])
    return {"program": _read(device)}


def _write(coordinator, device, program: dict) -> None:
    """Eseguita nell'executor: scrive i giorni cambiati, uno alla volta."""
    keymap = _day_keys(device)
    sent: list[str] = []
    for day in DAYS:
        with coordinator.mutex:
            ok = coordinator.cube.set_programme(device, keymap[day], program[day])
        if ok is False:
            raise HomeAssistantError(
                f"Il Cube ha rifiutato il programma di '{day}' "
                f"(già scritti: {', '.join(sent) or 'nessuno'}). "
                "Potrebbe essere il limite di duty cycle radio: riprova tra qualche minuto."
            )
        if ok:  # None = giorno invariato, saltato da set_programme
            sent.append(day)
            time.sleep(DAY_DELAY)
    with coordinator.mutex:
        try:
            coordinator.cube.update_config(device.rf_address)
        except OSError as err:
            _LOGGER.warning("Rilettura config dopo la scrittura fallita: %s", err)


async def _set_program(call: ServiceCall) -> None:
    coordinator, device = _resolve(call.hass, call.data["entity_id"])
    program = _normalize(call.data["program"])
    try:
        await call.hass.async_add_executor_job(_write, coordinator, device, program)
    except OSError as err:
        raise HomeAssistantError(f"Scrittura sul Cube fallita: {err}") from err
    await coordinator.async_request_refresh()





LETTER = vol.All(cv.string, vol.Match(r"^[A-Za-z]$"))
SEND_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Required("command"): LETTER,
        vol.Optional("argument", default=""): cv.string,
    }
)

def _send_raw(coordinator, command: str):
    """Eseguita nell'executor. DA COMPLETARE: serve il metodo di cube.py che invia un comando grezzo."""
    raise NotImplementedError

def _get_coordinator(hass: HomeAssistant, entry_id: str | None):
    if entry_id is None:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if len(entries) != 1:
            raise ServiceValidationError(
                "Indica 'entry_id': le integrazioni caricate sono "
                f"{len(entries)}, non una sola"
            )
        entry = entries[0]
    else:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(f"Entry '{entry_id}' non trovata o non caricata")

    coordinator = getattr(entry, "runtime_data", None) or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None:
        raise HomeAssistantError("Coordinator non trovato")
    return coordinator

async def _cube_send_command(call: ServiceCall) -> dict:
    coordinator = _get_coordinator(call.hass, call.data.get("entry_id"))
    
    def _run() -> str:
        with coordinator.mutex:
            return coordinator.cube.send_raw_command(call.data["command"], call.data["argument"])

    try:
        reply = await call.hass.async_add_executor_job(_run)
    except (OSError, TimeoutError) as err:
        raise HomeAssistantError(f"Invio al Cube fallito: {err}") from err
    return {"reply": reply}

@callback
def async_setup_services(hass: HomeAssistant) -> None:
    hass.services.async_register(
        DOMAIN, "get_program", _get_program,
        schema=GET_SCHEMA, supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "set_program", _set_program, 
        schema=SET_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, "cube_send_command", _cube_send_command,
        schema=SEND_SCHEMA, supports_response=SupportsResponse.OPTIONAL,
    )