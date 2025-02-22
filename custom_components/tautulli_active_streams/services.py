import logging
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

KILL_ALL_SCHEMA = vol.Schema({
    vol.Optional("message", default="Stream ended by admin."): cv.string,
})

KILL_USER_SCHEMA = vol.Schema({
    vol.Required("user"): cv.string,
    vol.Optional("message", default="Stream ended by admin."): cv.string,
})

async def async_setup_kill_stream_services(hass: HomeAssistant, entry, api) -> None:
    """Register kill stream services for Tautulli Active Streams."""
    _LOGGER.debug("Starting async_setup_kill_stream_services")
    
    # Define service handlers as closures so they capture hass and entry
    async def handle_kill_all_streams(call: ServiceCall) -> None:
        _LOGGER.debug("kill_all_streams called with data: %s", call.data)
        message = call.data.get("message")
        # Get coordinator from hass.data using the entry ID
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if not coordinator or "sessions" not in coordinator.data:
            _LOGGER.debug("No active sessions found (kill_all_streams).")
            return
        sessions = coordinator.data.get("sessions", [])
        if not sessions:
            _LOGGER.debug("No active sessions to terminate (kill_all_streams).")
            return
        _LOGGER.info("Attempting to terminate %d active sessions", len(sessions))
        tasks = []
        for session in sessions:
            session_id = session.get("session_id")
            if session_id:
                tasks.append(api.terminate_session(session_id=session_id, message=message))
                _LOGGER.debug("Queued termination for session %s", session_id)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for res in results if not isinstance(res, Exception))
        _LOGGER.info("Terminated %d out of %d sessions successfully.", success_count, len(sessions))

    async def handle_kill_user_stream(call: ServiceCall) -> None:
        _LOGGER.debug("kill_user_stream called with data: %s", call.data)
        target_user = call.data["user"].strip().lower()
        message = call.data.get("message")
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if not coordinator or "sessions" not in coordinator.data:
            _LOGGER.debug("No active sessions found (kill_user_stream).")
            return
        sessions = coordinator.data.get("sessions", [])
        matched_sessions = [
            s for s in sessions if target_user in (
                s.get("user", "").strip().lower(),
                s.get("friendly_name", "").strip().lower(),
                s.get("username", "").strip().lower()
            )
        ]
        if not matched_sessions:
            _LOGGER.debug("No sessions found for user: %s", target_user)
            return
        _LOGGER.info("Found %d active sessions for user '%s'. Attempting termination...", len(matched_sessions), target_user)
        tasks = []
        for session in matched_sessions:
            session_id = session.get("session_id")
            if session_id:
                tasks.append(api.terminate_session(session_id=session_id, message=message))
                _LOGGER.debug("Queued termination for session %s (user: %s)", session_id, target_user)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for res in results if not isinstance(res, Exception))
        _LOGGER.info("Successfully terminated %d out of %d sessions for user '%s'.", success_count, len(matched_sessions), target_user)

    try:
        hass.services.async_register(DOMAIN, "kill_all_streams", handle_kill_all_streams, schema=KILL_ALL_SCHEMA)
        _LOGGER.debug("Registered service kill_all_streams")
    except Exception as exc:
        _LOGGER.error("Error registering kill_all_streams: %s", exc, exc_info=True)

    try:
        hass.services.async_register(DOMAIN, "kill_user_stream", handle_kill_user_stream, schema=KILL_USER_SCHEMA)
        _LOGGER.debug("Registered service kill_user_stream")
    except Exception as exc:
        _LOGGER.error("Error registering kill_user_stream: %s", exc, exc_info=True)

    _LOGGER.debug("async_setup_kill_stream_services completed successfully")
