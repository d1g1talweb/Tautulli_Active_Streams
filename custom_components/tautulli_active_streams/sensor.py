import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import STATE_OFF, CONF_URL, CONF_API_KEY, CONF_VERIFY_SSL
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, DEFAULT_SESSION_COUNT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Tautulli stream sensors and diagnostic sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    num_sensors = entry.options.get("num_sensors", DEFAULT_SESSION_COUNT)

    entities = [TautulliStreamSensor(coordinator, entry, i) for i in range(num_sensors)]
    
    # Add diagnostic sensors
    diagnostic_sensors = [
        TautulliDiagnosticSensor(coordinator, entry, "stream_count"),
        TautulliDiagnosticSensor(coordinator, entry, "stream_count_direct_play"),
        TautulliDiagnosticSensor(coordinator, entry, "stream_count_direct_stream"),
        TautulliDiagnosticSensor(coordinator, entry, "stream_count_transcode"),
        TautulliDiagnosticSensor(coordinator, entry, "total_bandwidth"),
        TautulliDiagnosticSensor(coordinator, entry, "lan_bandwidth"),
        TautulliDiagnosticSensor(coordinator, entry, "wan_bandwidth"),
    ]
    
    async_add_entities(entities, True)
    async_add_entities(diagnostic_sensors, True)


class TautulliStreamSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tautulli stream sensor."""

    def __init__(self, coordinator, entry, index):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_tautulli_stream_{index + 1}"
        self._attr_name = f"Plex Session {index + 1} (Tautulli)"
        self._attr_icon = "mdi:plex"
        self._attr_device_info = self.device_info

    @property
    def state(self):
        """Return the state of the sensor."""
        sessions = self.coordinator.data.get("sessions", [])
        if len(sessions) > self._index:
            return sessions[self._index].get("state", STATE_OFF)
        return STATE_OFF

    @property
    def extra_state_attributes(self):
        """Return extra attributes for the sensor, including a cleaned-up image URL."""
        sessions = self.coordinator.data.get("sessions", [])
        if len(sessions) > self._index:
            session = sessions[self._index]

            base_url = self._entry.data.get(CONF_URL)
            api_key = self._entry.data.get(CONF_API_KEY)

            if not api_key or not base_url:
                return {}

            image_url = None
            if session.get("grandparent_thumb"):
                image_url = f"{base_url}/api/v2?apikey={api_key}&cmd=pms_image_proxy&img={session.get('grandparent_thumb')}&width=300&height=450&fallback=poster&refresh=true"
            elif session.get("thumb"):
                image_url = f"{base_url}/api/v2?apikey={api_key}&cmd=pms_image_proxy&img={session.get('thumb')}&width=300&height=450&fallback=poster&refresh=true"

            return {
                "user": session.get("user"),
                "progress_percent": session.get("progress_percent"),
                "media_type": session.get("media_type"),
                "full_title": session.get("full_title"),
                "grandparent_thumb": session.get("grandparent_thumb"),
                "thumb": session.get("thumb"),
                "image_url": image_url,  
                "parent_media_index": session.get("parent_media_index"),
                "media_index": session.get("media_index"),
                "year": session.get("year"),
                "product": session.get("product"),
                "player": session.get("player"),
                "device": session.get("device"),
                "platform": session.get("platform"),
                "location": session.get("location"),
                "ip_address": session.get("ip_address"),
                "ip_address_public": session.get("ip_address_public"),
                "local": session.get("local"),
                "relayed": session.get("relayed"),
                "bandwidth": session.get("bandwidth"),
                "video_resolution": session.get("video_resolution"),
                "stream_video_resolution": session.get("stream_video_resolution"),
                "transcode_decision": session.get("transcode_decision"),
            }
        return {}






    @property
    def device_info(self):
        """Return device info so all sensors are grouped under one device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Tautulli Active Streams",
            "manufacturer": "Richardvaio",
            "model": "Tautulli Active Streams",
            "entry_type": "service",
        }


class TautulliDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Tautulli diagnostic sensor."""

    def __init__(self, coordinator, entry, metric):
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._metric = metric
        self._attr_unique_id = f"{entry.entry_id}_tautulli_{metric}"
        self._attr_name = f"Tautulli {metric.replace('_', ' ').title()}"
        self._attr_icon = "mdi:chart-bar"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = self.device_info  # ✅ Make sure this is the same as session sensors

    @property
    def state(self):
        """Return the state of the diagnostic sensor."""
        diagnostics = self.coordinator.data.get("diagnostics", {})
        return diagnostics.get(self._metric, 0)

    @property
    def device_info(self):
        """Ensure diagnostic sensors are grouped under the same device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},  # ✅ Same device ID as session sensors
            "name": "Tautulli Active Streams",
            "manufacturer": "Richardvaio",
            "model": "Tautulli Active Streams",
            "entry_type": "service",
        }
