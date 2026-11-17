from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

import voluptuous as vol

from .const import DOMAIN, CONF_HOST, CONF_PORT

from homeassistant.util.dt import now

class MaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow principale."""

    VERSION = 1
    #CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _build_schema(self, defaults=None):
        """Schema riutilizzabile."""

        defaults = defaults or {}

        return vol.Schema({
            vol.Required(
                CONF_HOST,
                default=defaults.get(CONF_HOST, "")
            ): str,

            vol.Required(
                CONF_PORT,
                default=defaults.get(CONF_PORT, 62910)
            ): int

        })

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Configurazione iniziale."""

        if user_input is not None:

            return self.async_create_entry(
                title="ELV MAX!",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input)
        )

    async def async_step_reconfigure(
        self,
        user_input=None
    ) -> FlowResult:
        """Gestisce il pulsante Riconfigura."""

        entry = self._get_reconfigure_entry()

        if user_input is not None:

            self.hass.config_entries.async_update_entry(
                entry,
                data=user_input
            )

            await self.hass.config_entries.async_reload(
                entry.entry_id
            )

            return self.async_abort(
                reason="reconfigure_successful"
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._build_schema(entry.data)
        )