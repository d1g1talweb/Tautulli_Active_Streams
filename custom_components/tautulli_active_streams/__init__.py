import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL
from .api import TautulliAPI  # ✅ Import Updated API

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli Active Streams integration."""
    hass.data.setdefault(DOMAIN, {})

    # ✅ Retrieve settings from config
    url = entry.data[CONF_URL]
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)  # ✅ Get SSL verification option

    session = async_get_clientsession(hass, verify_ssl)  # ✅ Apply SSL setting
    api = TautulliAPI(url, api_key, session, verify_ssl)

    async def async_update_data():
        """Fetch data from Tautulli API (Silently ignore failures)."""
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
    hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        return False 

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unloading of the integration."""
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        return False
        
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)  # ✅ Remove only if successful

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update (Silently)."""
    unload_success = await async_unload_entry(hass, entry)

    if unload_success:
        await hass.config_entries.async_reload(entry.entry_id)
