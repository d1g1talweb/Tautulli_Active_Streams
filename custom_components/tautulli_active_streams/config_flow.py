import aiohttp
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
    CONF_STATS_MONTH_TO_DATE,
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

    def _show_setup_form(self, errors=None, user_input=None):
        user_input = user_input or {}
        data_schema = vol.Schema({
            vol.Optional("server_name", default=user_input.get("server_name", "")): str,
            vol.Required(CONF_URL, default=user_input.get(CONF_URL, "")): str,
            vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
            vol.Optional(CONF_VERIFY_SSL, default=user_input.get(CONF_VERIFY_SSL, True)): bool,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors or {}
        )

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL].strip()
            if not url.startswith(("http://", "https://")):
                url = "http://" + url
            user_input[CONF_URL] = url

            verify_ssl = user_input.get(CONF_VERIFY_SSL, True)
            server_name = user_input.get("server_name", "").strip()

            session = async_get_clientsession(self.hass, verify_ssl)
            api = TautulliAPI(url, user_input[CONF_API_KEY], session, verify_ssl)

            try:
                resp = await api.get_server_info()
                if not isinstance(resp, dict) or "response" not in resp:
                    raise ValueError(f"Malformed API response: {resp}")
                if resp["response"].get("result") != "success":
                    errors["base"] = "invalid_api_key"
                else:
                    if not server_name:
                        server_name = resp["response"].get("data", {}).get("pms_name", "")
            except aiohttp.ClientConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                LOGGER.exception("Unexpected error: %s", e)
                errors["base"] = "unknown"

            if errors:
                return self._show_setup_form(errors, user_input)

            self._flow_data = {
                "server_name": server_name,
                "url": url,
                "api_key": user_input[CONF_API_KEY],
                "verify_ssl": verify_ssl,
            }
            return await self.async_step_options()

        return self._show_setup_form()

    async def async_step_options(self, user_input=None):
        errors = {}
        if user_input is not None:
            session_interval = user_input.get(CONF_SESSION_INTERVAL, DEFAULT_SESSION_INTERVAL)
            num_sensors = user_input.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)
            image_proxy = user_input.get(CONF_IMAGE_PROXY, False)
            geo = user_input.get(CONF_ENABLE_IP_GEOLOCATION, False)
            adv_attrs = user_input.get(CONF_ADVANCED_ATTRIBUTES, False)
            enable_stats = user_input.get(CONF_ENABLE_STATISTICS, False)
            stats_mtd = user_input.get(CONF_STATS_MONTH_TO_DATE, False)
            stats_interval = user_input.get(CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL)
            stats_days = DEFAULT_STATISTICS_DAYS if enable_stats else 0

            return self.async_create_entry(
                title=self._flow_data.get("server_name") or "Tautulli Active Streams",
                data={
                    CONF_URL: self._flow_data["url"],
                    CONF_API_KEY: self._flow_data["api_key"],
                    CONF_VERIFY_SSL: self._flow_data["verify_ssl"],
                },
                options={
                    CONF_SESSION_INTERVAL: session_interval,
                    CONF_NUM_SENSORS: num_sensors,
                    CONF_IMAGE_PROXY: image_proxy,
                    CONF_ENABLE_IP_GEOLOCATION: geo,
                    CONF_ADVANCED_ATTRIBUTES: adv_attrs,
                    CONF_ENABLE_STATISTICS: enable_stats,
                    CONF_STATS_MONTH_TO_DATE: stats_mtd,
                    CONF_STATISTICS_INTERVAL: stats_interval,
                    CONF_STATISTICS_DAYS: stats_days,
                },
            )

        user_input = user_input or {}
        data_schema = vol.Schema({
            # Stream Monitoring
            vol.Required(CONF_SESSION_INTERVAL, default=DEFAULT_SESSION_INTERVAL): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_NUM_SENSORS, default=DEFAULT_NUM_SENSORS): vol.All(int, vol.Range(min=1)),
            vol.Optional(CONF_IMAGE_PROXY, default=False): bool,

            # Session Info Toggles
            vol.Optional(CONF_ENABLE_IP_GEOLOCATION, default=False): bool,
            vol.Optional(CONF_ADVANCED_ATTRIBUTES, default=False): bool,

            # Statistics
            vol.Optional(CONF_ENABLE_STATISTICS, default=False): bool,
            vol.Optional(CONF_STATS_MONTH_TO_DATE, default=False): bool,
            vol.Optional(CONF_STATISTICS_DAYS, default=DEFAULT_STATISTICS_DAYS): vol.All(int, vol.Range(min=1)),
            vol.Optional(CONF_STATISTICS_INTERVAL, default=DEFAULT_STATISTICS_INTERVAL): vol.All(int, vol.Range(min=60)),
        })

        return self.async_show_form(
            step_id="options",
            data_schema=data_schema,
            errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TautulliOptionsFlowHandler(config_entry)


class TautulliOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            # Stream Monitoring
            vol.Required(CONF_SESSION_INTERVAL, default=self.options.get(CONF_SESSION_INTERVAL, DEFAULT_SESSION_INTERVAL)): vol.All(int, vol.Range(min=1)),
            vol.Required(CONF_NUM_SENSORS, default=self.options.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)): vol.All(int, vol.Range(min=1)),
            vol.Optional(CONF_IMAGE_PROXY, default=self.options.get(CONF_IMAGE_PROXY, False)): bool,

            # Session Info Toggles
            vol.Optional(CONF_ENABLE_IP_GEOLOCATION, default=self.options.get(CONF_ENABLE_IP_GEOLOCATION, False)): bool,
            vol.Optional(CONF_ADVANCED_ATTRIBUTES, default=self.options.get(CONF_ADVANCED_ATTRIBUTES, False)): bool,

            # Statistics
            vol.Optional(CONF_ENABLE_STATISTICS, default=self.options.get(CONF_ENABLE_STATISTICS, False)): bool,
            vol.Optional(CONF_STATS_MONTH_TO_DATE, default=self.options.get(CONF_STATS_MONTH_TO_DATE, False)): bool,
            vol.Optional(CONF_STATISTICS_DAYS, default=self.options.get(CONF_STATISTICS_DAYS, DEFAULT_STATISTICS_DAYS)): vol.All(int, vol.Range(min=1)),
            vol.Optional(CONF_STATISTICS_INTERVAL, default=self.options.get(CONF_STATISTICS_INTERVAL, DEFAULT_STATISTICS_INTERVAL)): vol.All(int, vol.Range(min=60)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
