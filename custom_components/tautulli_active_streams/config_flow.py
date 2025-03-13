import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    DEFAULT_SESSION_INTERVAL,
    DEFAULT_NUM_SENSORS,
    DEFAULT_STATISTICS_INTERVAL,
    DEFAULT_STATISTICS_DAYS,
    CONF_SESSION_INTERVAL,
    CONF_NUM_SENSORS,
    CONF_ENABLE_STATISTICS,
    CONF_STATISTICS_INTERVAL,
    CONF_STATISTICS_DAYS,
    CONF_ADVANCED_ATTRIBUTES,
    CONF_IMAGE_PROXY,
    CONF_ENABLE_IP_GEOLOCATION,
    LOGGER,
)
from .api import TautulliAPI

class TautulliConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handles the configuration flow for Tautulli Active Streams."""
    VERSION = 1

    def __init__(self):
        self._flow_data = {}
        # to track if user turned stats on in step2
        self._stats_enabled = False

    def _show_setup_form(self, errors=None, user_input=None):
        """
        Step 1 (user):
          - server_name
          - url
          - api_key
          - verify_ssl
          - image_proxy
        """
        user_input = user_input or {}
        data_schema = vol.Schema({
            vol.Optional("server_name", default=user_input.get("server_name", "")): str,
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)): bool,
            vol.Optional(CONF_IMAGE_PROXY, default=user_input.get(CONF_IMAGE_PROXY, False)): bool,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {}
        )

    async def async_step_user(self, user_input=None):
        """Step 1 logic: Validate Tautulli, store partial, go to step2."""
        errors = {}
        if user_input is not None:
            # Check if already configured
            existing_entry = self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            if existing_entry:
                return self.async_abort(reason="already_configured")

            # Test Tautulli connectivity
            url = user_input[CONF_URL].strip()
            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            session = async_get_clientsession(self.hass, verify_ssl)
            api = TautulliAPI(url, user_input[CONF_API_KEY], session, verify_ssl)
            try:
                resp = await api.get_activity()
                if not resp:
                    raise ValueError("Empty API response")
            except Exception:
                errors["base"] = "cannot_connect"
                return self._show_setup_form(errors, user_input)

            # Store partial data
            self._flow_data["server_name"] = user_input.get("server_name", "")
            self._flow_data["url"] = url
            self._flow_data["api_key"] = user_input[CONF_API_KEY]
            self._flow_data["verify_ssl"] = verify_ssl
            self._flow_data["image_proxy"] = user_input.get(CONF_IMAGE_PROXY, False)

            # go to step2
            return await self.async_step_options_stats()

        return self._show_setup_form()

    async def async_step_options_stats(self, user_input=None):
        """
        Step 2: Show the rest of the options including IP geolocation,
        advanced attributes, and statistics.
        """
        errors = {}
        if user_input is not None:
            self._flow_data["session_interval"] = user_input.get(CONF_SESSION_INTERVAL, DEFAULT_SESSION_INTERVAL)
            self._flow_data["num_sensors"] = user_input.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)
            self._flow_data["advanced_attrs"] = user_input.get(CONF_ADVANCED_ATTRIBUTES, False)

            # IP Geolocation toggle
            self._flow_data[CONF_ENABLE_IP_GEOLOCATION] = user_input.get(CONF_ENABLE_IP_GEOLOCATION, False)

            # Statistics
            self._flow_data["enable_statistics"] = user_input.get(CONF_ENABLE_STATISTICS, False)
            self._flow_data["stats_interval"] = user_input.get(CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL)
            self._flow_data["stats_days"] = user_input.get(CONF_STATISTICS_DAYS, DEFAULT_STATISTICS_DAYS)

            return self._create_entry()

        data_schema = vol.Schema({
            vol.Optional(CONF_SESSION_INTERVAL, default=DEFAULT_SESSION_INTERVAL): int,
            vol.Optional(CONF_NUM_SENSORS, default=DEFAULT_NUM_SENSORS): int,
            vol.Optional(CONF_ENABLE_IP_GEOLOCATION, default=False): bool,
            vol.Optional(CONF_IMAGE_PROXY, default=user_input.get(CONF_IMAGE_PROXY, False)): bool,
            vol.Optional(CONF_ADVANCED_ATTRIBUTES, default=False): bool,
            vol.Optional(CONF_ENABLE_STATISTICS, default=False): bool,
            vol.Optional(CONF_STATISTICS_INTERVAL, default=DEFAULT_STATISTICS_INTERVAL): int,
            vol.Optional(CONF_STATISTICS_DAYS, default=DEFAULT_STATISTICS_DAYS): int,
        })

        return self.async_show_form(
            step_id="options_stats",
            data_schema=data_schema,
            errors=errors
        )


    def _create_entry(self):
        """
        Final: combine user input from step1 + step2 (+ step3) into a single config entry.
        - connection info => entry.data
        - everything else => entry.options
        """
        final_title = self._flow_data.get("server_name") or "Tautulli Active Streams"
        return self.async_create_entry(
            title=final_title,
            data={
                CONF_URL: self._flow_data["url"],
                CONF_API_KEY: self._flow_data["api_key"],
                CONF_VERIFY_SSL: self._flow_data["verify_ssl"],
            },
            options={
                CONF_IMAGE_PROXY: self._flow_data.get("image_proxy", False),
                CONF_SESSION_INTERVAL: self._flow_data.get("session_interval", DEFAULT_SESSION_INTERVAL),
                CONF_NUM_SENSORS: self._flow_data.get("num_sensors", DEFAULT_NUM_SENSORS),
                CONF_ADVANCED_ATTRIBUTES: self._flow_data.get("advanced_attrs", False),
                CONF_ENABLE_STATISTICS: self._flow_data.get("enable_statistics", False),
                CONF_STATISTICS_INTERVAL: self._flow_data.get("stats_interval", DEFAULT_STATISTICS_INTERVAL),
                CONF_STATISTICS_DAYS: self._flow_data.get("stats_days", DEFAULT_STATISTICS_DAYS),
                CONF_ENABLE_IP_GEOLOCATION: self._flow_data.get(CONF_ENABLE_IP_GEOLOCATION, False),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TautulliOptionsFlowHandler(config_entry)


class TautulliOptionsFlowHandler(config_entries.OptionsFlow):
    """
    Single-step reconfiguration (Configure) flow:
    Show the same options as in the install step2, all in one form.
    """
    def __init__(self, config_entry):
        self._config_entry = config_entry
        self._initial_opts = dict(config_entry.options)
        self._updated = dict(self._initial_opts)

    async def async_step_init(self, user_input=None):
        """Display and handle the options form."""
        if user_input is not None:
            self._updated[CONF_SESSION_INTERVAL] = user_input.get(CONF_SESSION_INTERVAL, DEFAULT_SESSION_INTERVAL)
            self._updated[CONF_NUM_SENSORS]      = user_input.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)
            self._updated[CONF_ENABLE_IP_GEOLOCATION] = user_input.get(CONF_ENABLE_IP_GEOLOCATION, False)
            self._updated[CONF_ADVANCED_ATTRIBUTES]   = user_input.get(CONF_ADVANCED_ATTRIBUTES, False)
            self._updated[CONF_ENABLE_STATISTICS]     = user_input.get(CONF_ENABLE_STATISTICS, False)
            self._updated[CONF_STATISTICS_INTERVAL]   = user_input.get(CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL)
            self._updated[CONF_STATISTICS_DAYS]       = user_input.get(CONF_STATISTICS_DAYS, DEFAULT_STATISTICS_DAYS)

            return self.async_create_entry(title="", data=self._updated)

        data_schema = vol.Schema({
            vol.Required(
                CONF_SESSION_INTERVAL,
                default=self._initial_opts.get(CONF_SESSION_INTERVAL, DEFAULT_SESSION_INTERVAL)
            ): int,
            vol.Required(
                CONF_NUM_SENSORS,
                default=self._initial_opts.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)
            ): int,
            vol.Optional(
                CONF_ENABLE_IP_GEOLOCATION,
                default=self._initial_opts.get(CONF_ENABLE_IP_GEOLOCATION, False)
            ): bool,
            vol.Optional(
                CONF_ADVANCED_ATTRIBUTES,
                default=self._initial_opts.get(CONF_ADVANCED_ATTRIBUTES, False)
            ): bool,
            vol.Optional(
                CONF_ENABLE_STATISTICS,
                default=self._initial_opts.get(CONF_ENABLE_STATISTICS, False)
            ): bool,
            vol.Optional(
                CONF_STATISTICS_INTERVAL,
                default=self._initial_opts.get(CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL)
            ): int,
            vol.Optional(
                CONF_STATISTICS_DAYS,
                default=self._initial_opts.get(CONF_STATISTICS_DAYS, DEFAULT_STATISTICS_DAYS)
            ): int,
        })
        return self.async_show_form(step_id="init", data_schema=data_schema)
