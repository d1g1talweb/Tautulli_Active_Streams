import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli Active Streams integration."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    
    # ✅ Ensure the API instance is created properly
    from .api import TautulliAPI
    api = TautulliAPI(entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_API_KEY], session)

    async def async_update_data():
        """Fetch data from Tautulli API."""
        try:
            data = await api.get_activity()
            if not data:
                _LOGGER.error("❌ No data received from Tautulli API!")
                return {}
            return data
        except Exception as err:
            _LOGGER.error(f"⚠️ API request failed: {err}")
            return {}  # ✅ Return empty data instead of raising an error

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        # ✅ Use async_create_task to prevent blocking the event loop
        hass.async_create_task(hass.config_entries.async_forward_entry_setups(entry, PLATFORMS))
    except Exception as err:
        _LOGGER.error(f"❌ Failed to set up sensors: {err}")
        return False  # ✅ Ensure Home Assistant doesn't try to unload a non-loaded sensor

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of the integration."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.warning(f"⚠️ Attempted to unload non-existent entry {entry.entry_id}")
        return False  # ✅ Prevents unnecessary unload attempts

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)  # ✅ Remove only if successful

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update and ensure sensors reload properly."""
    _LOGGER.debug("🔄 Reloading Tautulli Active Streams integration due to options update")

    # ✅ Unload the existing sensors first
    if entry.entry_id in hass.data[DOMAIN]:
        await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    unload_success = await async_unload_entry(hass, entry)

    if unload_success:
        await hass.config_entries.async_reload(entry.entry_id)
    
    """Handle options update and ensure proper reloading."""
    _LOGGER.debug("🔄 Reloading Tautulli Active Streams integration due to options update")

    unload_success = await async_unload_entry(hass, entry)

    if unload_success:
        await hass.config_entries.async_reload(entry.entry_id)
