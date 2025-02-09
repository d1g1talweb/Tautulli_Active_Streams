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

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

 
DEFAULT_SESSION_SENSORS = DEFAULT_SESSION_COUNT

async def async_remove_extra_session_sensors(hass: HomeAssistant, entry: ConfigEntry):
    """Remove extra session sensor entities that exceed the new configuration."""
    registry = er.async_get(hass)
    
    session_sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_SENSORS)
    _LOGGER.debug("New num_sensors option is: %s", session_sensor_count)
    
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    
    for ent in entries:
        if (ent.domain == "sensor" and 
            ent.unique_id.startswith("plex_session_") and 
            ent.unique_id.endswith("_tautulli")):
            try:
       
                number_str = ent.unique_id[len("plex_session_"):-len("_tautulli")]
                sensor_number = int(number_str)
            except ValueError:
                _LOGGER.debug("Unable to parse sensor number from unique_id: %s", ent.unique_id)
                continue
            
            if sensor_number > session_sensor_count:
                _LOGGER.debug("Removing extra sensor entity: %s (sensor number: %s)", ent.entity_id, sensor_number)
                registry.async_remove(ent.entity_id)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli Active Streams integration."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    session = async_get_clientsession(hass, verify_ssl)
    api = TautulliAPI(url, api_key, session, verify_ssl)

    async def async_update_data():
        """Fetch data from Tautulli API (silently ignore failures)."""
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
    coordinator.sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_SENSORS)
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
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update for Tautulli Active Streams."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    new_sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_SENSORS)
    
    if new_sensor_count > coordinator.sensor_count:
        _LOGGER.debug(
            "Increased sensor count detected (old: %s, new: %s); reloading integration to add new sensors.",
            coordinator.sensor_count, new_sensor_count
        )

        await hass.config_entries.async_reload(entry.entry_id)
    else:
        
        await async_remove_extra_session_sensors(hass, entry)
        coordinator.update_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        await coordinator.async_request_refresh()
        coordinator.sensor_count = new_sensor_count
