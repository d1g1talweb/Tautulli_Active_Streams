import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_SESSION_COUNT
from .api import TautulliAPI


class TautulliConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the configuration flow for Tautulli Active Streams."""

    VERSION = 1

    async def _show_setup_form(self, errors=None, user_input=None):
        """Show the setup form to the user."""
        user_input = user_input or {}

        data_schema = vol.Schema({
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str, 
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)): bool, 
            vol.Required(CONF_SCAN_INTERVAL, default=user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            vol.Required("num_sensors", default=user_input.get("num_sensors", DEFAULT_SESSION_COUNT)): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {}
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration setup."""
        errors = {}

        if user_input is not None:
           
            existing_entry = self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            if existing_entry:
                return self.async_abort(reason="already_configured")

         
            url = user_input[CONF_URL].strip()
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)

           
            session = async_get_clientsession(self.hass, verify_ssl)
            api = TautulliAPI(url, user_input[CONF_API_KEY], session, verify_ssl)

         
            try:
                response = await api.get_activity()
                if not response:
                    raise ValueError("Invalid API response")
            except Exception:
                errors["base"] = "cannot_connect"
                return await self._show_setup_form(errors, user_input)

          
            return self.async_create_entry(
                title="Tautulli Active Streams",
                data={
                    CONF_URL: url,  
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_VERIFY_SSL: verify_ssl,
                },
                options={
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    "num_sensors": user_input.get("num_sensors", DEFAULT_SESSION_COUNT),
                },
            )

        return await self._show_setup_form()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return TautulliOptionsFlowHandler(config_entry)


class TautulliOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Tautulli Active Streams options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Manage the options (Configure menu)."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
            vol.Required("num_sensors", default=self.options.get("num_sensors", DEFAULT_SESSION_COUNT)): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )
