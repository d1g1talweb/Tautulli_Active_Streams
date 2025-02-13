import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_SESSION_COUNT
from .api import TautulliAPI
from .views import TautulliImageView

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli Active Streams integration with image proxy always enabled."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    session = async_get_clientsession(hass, verify_ssl)
    api = TautulliAPI(url, api_key, session, verify_ssl)

    # --- Image Proxy Setup ---
    # Store configuration data for the image proxy view so that the view can fetch images from Tautulli.
    hass.data["tautulli_integration_config"] = {
        "base_url": url,
        "api_key": api_key,
    }
    # Always register the image proxy view.
    hass.http.register_view(TautulliImageView)
    # -------------------------

    async def async_update_data():
        try:
            data = await api.get_activity()
            return data if data else {}
        except Exception:
            return {}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )

    await coordinator.async_config_entry_first_refresh()
    coordinator.sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_COUNT)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of the integration."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update for Tautulli Active Streams."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    new_sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_COUNT)
    
    if new_sensor_count > coordinator.sensor_count:
        _LOGGER.debug(
            "Increased sensor count detected (old: %s, new: %s); reloading integration to add new sensors.",
            coordinator.sensor_count, new_sensor_count
        )
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        coordinator.update_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await coordinator.async_request_refresh()
        coordinator.sensor_count = new_sensor_count
