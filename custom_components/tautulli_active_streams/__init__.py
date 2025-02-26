import logging
import asyncio
import time
from datetime import timedelta, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .views import TautulliImageView
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, DEFAULT_SESSION_COUNT
from .api import TautulliAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]
DEFAULT_SESSION_SENSORS = DEFAULT_SESSION_COUNT

def format_seconds_to_min_sec(total_seconds: float) -> str:
    total_seconds = int(total_seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}m {secs}s"

class TautulliCoordinator(DataUpdateCoordinator):
    """Custom Coordinator to fetch from Tautulli and track sessions."""

    def __init__(self, hass: HomeAssistant, logger, api: TautulliAPI, update_interval: timedelta):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api
        # Dictionary of session_id -> float(timestamp) for the first time we saw that session
        self.start_times = {}
        # Dictionary of session_id -> float(timestamp) for the first time we saw it paused
        self.paused_since = {}
        
    async def _async_update_data(self):
        """Fetch data from Tautulli API and track sessions."""
        try:
            # Tautulli data typically has: {"sessions": [...], "diagnostics": {...}}
            data = await self.api.get_activity()
        except Exception as err:
            _LOGGER.warning("Failed to update Tautulli data: %s", err)
            data = {}

        sessions = data.get("sessions", [])
        now = time.time()

        # Track current active session IDs to detect removals
        current_ids = set()

        for s in sessions:
            sid = s.get("session_id")
            if not sid:
                continue  # Skip if no valid session_id

            current_ids.add(sid)

            # 1) Track session start times
            if sid not in self.start_times:
                self.start_times[sid] = now  # first time seeing this session

        # Clean up any old sessions that disappeared
        for old_sid in list(self.start_times.keys()):
            if old_sid not in current_ids:
                del self.start_times[old_sid]
                # Also remove from paused_since if present
                if old_sid in self.paused_since:
                    del self.paused_since[old_sid]

        # Attach 'start_time_raw', 'start_time', and handle paused duration
        for s in sessions:
            sid = s.get("session_id")
            if not sid:
                continue

            # Convert session start epoch to HH:MM:SS
            raw_ts = self.start_times.get(sid)
            if raw_ts:
                dt = datetime.fromtimestamp(raw_ts)
                s["start_time_raw"] = raw_ts
                s["start_time"] = dt.strftime("%H:%M:%S")
            else:
                s["start_time_raw"] = None
                s["start_time"] = None

            # 2) Compute paused duration
            state = s.get("state", "").strip().lower()
            if state == "paused":
                if sid not in self.paused_since:
                    # record first paused time
                    self.paused_since[sid] = now
                paused_sec = now - self.paused_since[sid]
                s["Stream_paused_duration_sec"] = paused_sec
                s["Stream_paused_duration"] = format_seconds_to_min_sec(paused_sec)
            else:
                # if was paused before, remove from paused_since
                if sid in self.paused_since:
                    del self.paused_since[sid]
                s["Stream_paused_duration_sec"] = 0
                s["Stream_paused_duration"] = "0m 0s"

        data["sessions"] = sessions
        return data

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tautulli Active Streams integration."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data[CONF_URL]
    api_key = entry.data[CONF_API_KEY]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, True)

    session = async_get_clientsession(hass, verify_ssl)
    api = TautulliAPI(url, api_key, session, verify_ssl)
    
    # --- Image Proxy Setup ---
    hass.data["tautulli_integration_config"] = {"base_url": url, "api_key": api_key}
    hass.http.register_view(TautulliImageView)
    # -------------------------

    update_interval = timedelta(seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    coordinator = TautulliCoordinator(
        hass=hass,
        logger=_LOGGER,
        api=api,
        update_interval=update_interval
    )

    # Run the first update to populate data
    await coordinator.async_config_entry_first_refresh()

    # Store the number of session sensors
    coordinator.sensor_count = entry.options.get("num_sensors", DEFAULT_SESSION_SENSORS)

    # Save coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward entry setups
    try:
        await asyncio.shield(hass.config_entries.async_forward_entry_setups(entry, PLATFORMS))
    except asyncio.CancelledError:
        _LOGGER.error("Setup of sensor platforms was cancelled")
        return False
    except Exception as ex:
        _LOGGER.error("Error forwarding entry setups: %s", ex)
        return False

    # Register kill stream services
    try:
        from .services import async_setup_kill_stream_services
        await async_setup_kill_stream_services(hass, entry, api)
    except Exception as exc:
        _LOGGER.error("Exception during kill stream service registration: %s", exc, exc_info=True)

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

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

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        # Unregister the kill stream services.
        for service in ["kill_all_streams", "kill_user_stream"]:
            hass.services.async_remove(DOMAIN, service)
        # Continue with unloading platforms...
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id, None)
        return unload_ok
    return False

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
