import logging
import time
from datetime import datetime, timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import STATE_OFF, CONF_URL, CONF_API_KEY
from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
import aiohttp
import xml.etree.ElementTree as ET

from .const import (
    DOMAIN,
    DEFAULT_NUM_SENSORS,
    CONF_NUM_SENSORS,
    CONF_ENABLE_STATISTICS,
    CONF_IMAGE_PROXY,
    CONF_ADVANCED_ATTRIBUTES  # make sure these are imported,
)

_LOGGER = logging.getLogger(__name__)


def format_seconds_to_min_sec(total_seconds: float) -> str:
    """Convert seconds into 'Mm Ss' format."""
    total_seconds = int(total_seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes}m {secs}s"


async def _fetch_plex_credits(plex_base_url, plex_token, rating_key):
    """
    Query Plex for chapters & markers by hitting:
      {plex_base_url}/library/metadata/{rating_key}?includeChapters=1&includeMarkers=1&X-Plex-Token={plex_token}

    We parse the returned XML for either:
      <Marker type="credits" startTimeOffset="..." />
    or
      <Chapter tag="...Credits..." startTimeOffset="..." />
    If found, we return the startTimeOffset (ms). Otherwise None.
    """
    url = (
        f"{plex_base_url}/library/metadata/{rating_key}"
        f"?includeChapters=1&includeMarkers=1"
        f"&X-Plex-Token={plex_token}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    _LOGGER.warning(
                        "Failed to fetch XML for rating_key=%s: status=%s, reason=%s",
                        rating_key, resp.status, resp.reason
                    )
                    return None

                # Retrieve the full XML text
                xml_body = await resp.text()

                # Parse XML with ElementTree
                root = ET.fromstring(xml_body)  # <MediaContainer ...>

                # Usually <Video> is the first child
                video_el = root.find("Video")
                if video_el is None:
                    return None

                summary_text = video_el.attrib.get("summary", "")

                # 1) Check <Marker type="credits">
                markers = video_el.findall("Marker")
                for marker in markers:
                    mtype = marker.attrib.get("type", "")
                    if mtype == "credits":
                        return int(marker.attrib.get("startTimeOffset", 0))

                # 2) Otherwise check <Chapter> with "credit" in the 'tag'
                chapters = video_el.findall("Chapter")
                for ch in chapters:
                    ch_tag = ch.attrib.get("tag", "").lower()
                    if "credit" in ch_tag:
                        return int(ch.attrib.get("startTimeOffset", 0))

    except Exception as err:
        _LOGGER.warning("Error fetching Plex credits for rating_key=%s: %s", rating_key, err)

    return None


async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up the Tautulli stream sensors, diagnostic sensors, and user stats sensors
    using two different coordinators:
      - sessions_coordinator for sessions/diagnostics
      - history_coordinator for user-based stats
    """

    # Retrieve both coordinators
    data = hass.data[DOMAIN][entry.entry_id]
    sessions_coordinator = data["sessions_coordinator"]
    history_coordinator = data["history_coordinator"]

    # Number of active stream sensors to create
    num_sensors = entry.options.get(CONF_NUM_SENSORS, DEFAULT_NUM_SENSORS)

    # 1) Create a sensor for each "active stream" slot
    session_sensors = []
    for i in range(num_sensors):
        session_sensors.append(
            TautulliStreamSensor(sessions_coordinator, entry, i)
        )

    # 2) Create diagnostic sensors
    diagnostic_sensors = [
        TautulliDiagnosticSensor(sessions_coordinator, entry, "stream_count"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "stream_count_direct_play"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "stream_count_direct_stream"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "stream_count_transcode"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "total_bandwidth"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "lan_bandwidth"),
        TautulliDiagnosticSensor(sessions_coordinator, entry, "wan_bandwidth"),
    ]

    # 3) (Optional) Create user stats sensors if "enable_statistics" is on
    stats_sensors = []
    if entry.options.get(CONF_ENABLE_STATISTICS, False):
        user_stats = history_coordinator.data.get("user_stats", {})
        if user_stats:
            i = 0
            for username, stats_dict in user_stats.items():
                stats_sensors.append(
                    TautulliUserStatsSensor(
                        coordinator=history_coordinator,
                        entry=entry,
                        username=username,
                        stats=stats_dict,
                        index=i
                    )
                )
                i += 1
        else:
            _LOGGER.debug(
                "enable_statistics is True, but no user_stats found in history_coordinator.data."
            )

    # Add everything to Home Assistant
    async_add_entities(session_sensors, True)
    async_add_entities(diagnostic_sensors, True)
    async_add_entities(stats_sensors, True)


class TautulliStreamSensor(CoordinatorEntity, SensorEntity):
    """
    Representation of a Tautulli stream sensor,
    reading from the sessions_coordinator for session data.
    """

    def __init__(self, coordinator, entry, index):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._index = index
        # The unique_id ends with _tautulli so the removal code can match
        self._attr_unique_id = f"plex_session_{index + 1}_{entry.entry_id}_tautulli"
        self._attr_name = f"Plex Session {index + 1} (Tautulli)"
        self._attr_icon = "mdi:plex"

        # local paused duration tracking
        self._paused_start = None
        self._paused_duration_sec = 0
        self._paused_duration_str = "0m 0s"
        self._unsub_timer = None

        # new: track credits
        self._credits_start_time = None  # e.g. "1m 23s"
        self._in_credits = False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_active_streams")},
            "name": f"{self._entry.title} Active Streams",
            "manufacturer": "Richardvaio",
            "model": "Tautulli Active Streams",
            "entry_type": "service",
        }

    async def async_added_to_hass(self):
        """
        Called when this sensor is added to HA.
        We set up a per-second timer to update pause durations and credits.
        """
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._update_every_second, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self):
        """
        Called when removing the sensor, so we cancel our timer.
        """
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        await super().async_will_remove_from_hass()

    async def _update_every_second(self, now):
        """
        Called every second. Update paused duration and
        check for credits if Plex is enabled.
        """
        # 1) Update local paused-time tracking
        self._update_pause_duration()

        # 2) Update Plex credits logic
        await self._update_plex_credits()

        # Finally, write new state attributes
        self.async_write_ha_state()

    def _update_pause_duration(self):
        """
        Increments local pause counter if the state is 'paused'.
        Resets if it's not paused.
        """
        current_state = self.state.lower()
        if current_state == "paused":
            if self._paused_start is None:
                self._paused_start = time.time()
            elapsed = time.time() - self._paused_start
            self._paused_duration_sec = int(elapsed)
            self._paused_duration_str = format_seconds_to_min_sec(self._paused_duration_sec)
        else:
            self._paused_start = None
            self._paused_duration_sec = 0
            self._paused_duration_str = "0m 0s"

    ### NOTE: THIS METHOD IS NOW INDENTED INSIDE THE CLASS
    async def _update_plex_credits(self):
        """
        Check if user enabled Plex integration, fetch chapters, determine if credits are active.
        """
        plex_enabled = self._entry.data.get("plex_enabled")
        plex_token = self._entry.data.get("plex_token")
        plex_base_url = self._entry.data.get("plex_base_url")

        if not plex_enabled or not plex_token or not plex_base_url:
            # if user didn't enable or token is missing, skip
            self._credits_start_time = None
            self._in_credits = False
            return

        sessions = self.coordinator.data.get("sessions", [])
        if len(sessions) <= self._index:
            self._credits_start_time = None
            self._in_credits = False
            return

        session = sessions[self._index]
        rating_key = session.get("rating_key")

        # view_offset is a string from Tautulli, parse it as int
        view_offset_str = session.get("view_offset")
        if not rating_key or not view_offset_str:
            # skip if no rating_key or no offset
            self._credits_start_time = None
            self._in_credits = False
            return

        try:
            view_offset = int(view_offset_str)
        except ValueError:
            _LOGGER.warning("Could not parse view_offset=%s for rating_key=%s", view_offset_str, rating_key)
            self._credits_start_time = None
            self._in_credits = False
            return

        # fetch chapter data
        start_ms = await _fetch_plex_credits(plex_base_url, plex_token, rating_key)
        if start_ms:
            # are we >= credit start?
            self._in_credits = (view_offset >= start_ms)

            # store a user-readable time
            minutes = start_ms // 60000
            seconds = (start_ms % 60000) // 1000
            self._credits_start_time = f"{minutes}m {seconds}s"
        else:
            # no credits info found
            self._credits_start_time = None
            self._in_credits = False
    ### END OF THE METHOD

    @property
    def state(self):
        """Return the current Tautulli session state (playing, paused, etc.)"""
        sessions = self.coordinator.data.get("sessions", [])
        if len(sessions) > self._index:
            return sessions[self._index].get("state", STATE_OFF)
        return STATE_OFF

    @property
    def extra_state_attributes(self):
        """
        Return extra attributes for the sensor (basic or advanced),
        plus new 'in_credits' info if Plex integration is enabled.
        """
        plex_enabled = self._entry.data.get("plex_enabled")
        plex_token = self._entry.data.get("plex_token")
        plex_base_url = self._entry.data.get("plex_base_url")

        sessions = self.coordinator.data.get("sessions", [])
        if len(sessions) <= self._index:
            return {}

        session = sessions[self._index]

        base_url = self._entry.data.get(CONF_URL)
        api_key = self._entry.data.get(CONF_API_KEY)
        image_proxy = self._entry.options.get(CONF_IMAGE_PROXY, False)
        advanced = self._entry.options.get(CONF_ADVANCED_ATTRIBUTES, False)

        attributes = {}

        # Build an image URL if base_url & api_key
        thumb_url = session.get("grandparent_thumb") or session.get("thumb")
        if thumb_url and base_url and api_key:
            if image_proxy:
                attributes["image_url"] = (
                    f"/api/tautulli/image"
                    f"?entry_id={self._entry.entry_id}"
                    f"&img={thumb_url}"
                    "&width=300&height=450&fallback=poster&refresh=true"
                )
            else:
                attributes["image_url"] = (
                    f"{base_url}/api/v2"
                    f"?apikey={api_key}"
                    f"&cmd=pms_image_proxy"
                    f"&img={thumb_url}"
                    "&width=300&height=450&fallback=poster&refresh=true"
                )

        # Build an art URL if base_url & api_key
        art_path = session.get("art")
        if art_path and base_url and api_key:
            if image_proxy:
                attributes["art_url"] = (
                    f"/api/tautulli/image"
                    f"?entry_id={self._entry.entry_id}"
                    f"&img={art_path}"
                    "&width=1920&height=1080&fallback=art&refresh=true"
                )
            else:
                attributes["art_url"] = (
                    f"{base_url}/api/v2"
                    f"?apikey={api_key}"
                    f"&cmd=pms_image_proxy"
                    f"&img={art_path}"
                    "&width=1920&height=1080&fallback=art&refresh=true"
                )

        # Basic
        attributes["user"] = session.get("user")
        attributes["progress_percent"] = session.get("progress_percent")
        attributes["media_type"] = session.get("media_type")
        attributes["full_title"] = session.get("full_title")
        attributes["parent_media_index"] = session.get("parent_media_index")
        attributes["media_index"] = session.get("media_index")
        attributes["year"] = session.get("year")
        attributes["product"] = session.get("product")
        attributes["player"] = session.get("player")
        attributes["device"] = session.get("device")
        attributes["platform"] = session.get("platform")
        attributes["location"] = session.get("location")
        attributes["ip_address"] = session.get("ip_address")
        attributes["ip_address_public"] = session.get("ip_address_public")
        attributes["geo_city"] = session.get("geo_city")
        attributes["geo_region"] = session.get("geo_region")
        attributes["geo_country"] = session.get("geo_country")
        attributes["geo_code"] = session.get("geo_code")
        attributes["local"] = session.get("local")
        attributes["relayed"] = session.get("relayed")
        attributes["bandwidth"] = session.get("bandwidth")
        attributes["video_resolution"] = session.get("video_resolution")
        attributes["stream_video_resolution"] = session.get("stream_video_resolution")
        attributes["transcode_decision"] = session.get("transcode_decision")
        attributes["stream_paused_duration"] = self._paused_duration_str

        # If advanced is off, return now
        if not advanced:
            return attributes

        # Advanced is ON, so add more
        if session.get("stream_duration"):
            total_ms = float(session["stream_duration"])
            hours = int(total_ms // 3600000)
            minutes = int((total_ms % 3600000) // 60000)
            seconds = int((total_ms % 60000) // 1000)
            formatted_duration = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            formatted_duration = None

        if session.get("view_offset") and session.get("stream_duration"):
            remain_ms = float(session["stream_duration"]) - float(session["view_offset"])
            remain_seconds = remain_ms / 1000
            remain_hours = int(remain_seconds // 3600)
            remain_minutes = int((remain_seconds % 3600) // 60)
            remain_secs = int(remain_seconds % 60)
            formatted_remaining = f"{remain_hours}:{remain_minutes:02d}:{remain_secs:02d}"

            eta = datetime.now() + timedelta(seconds=remain_seconds)
            hour_12 = eta.strftime("%I").lstrip("0") or "12"
            minute = eta.strftime("%M")
            ampm = eta.strftime("%p").lower()
            formatted_eta = f"{hour_12}:{minute} {ampm}"
        else:
            formatted_remaining = None
            formatted_eta = None

        attributes.update({
            "user_friendly_name": session.get("friendly_name"),
            "username": session.get("username"),
            "user_thumb": session.get("user_thumb"),
            "session_id": session.get("session_id"),
            "library_name": session.get("library_name"),
            "grandparent_title": session.get("grandparent_title"),
            "title": session.get("title"),
            "container": session.get("container"),
            "aspect_ratio": session.get("aspect_ratio"),
            "video_codec": session.get("video_codec"),
            "video_framerate": session.get("video_framerate"),
            "video_profile": session.get("video_profile"),
            "video_dovi_profile": session.get("video_dovi_profile"),
            "video_dynamic_range": session.get("video_dynamic_range"),
            "video_color_space": session.get("video_color_space"),
            "audio_codec": session.get("audio_codec"),
            "audio_channels": session.get("audio_channels"),
            "audio_channel_layout": session.get("audio_channel_layout"),
            "audio_profile": session.get("audio_profile"),
            "audio_bitrate": session.get("audio_bitrate"),
            "audio_language": session.get("audio_language"),
            "audio_language_code": session.get("audio_language_code"),
            "subtitle_language": session.get("subtitle_language"),
            "container_decision": session.get("stream_container_decision"),
            "audio_decision": session.get("audio_decision"),
            "video_decision": session.get("video_decision"),
            "subtitle_decision": session.get("subtitle_decision"),
            "transcode_container": session.get("transcode_container"),
            "transcode_audio_codec": session.get("transcode_audio_codec"),
            "transcode_video_codec": session.get("transcode_video_codec"),
            "transcode_throttled": session.get("transcode_throttled"),
            "transcode_progress": session.get("transcode_progress"),
            "transcode_speed": session.get("transcode_speed"),
            "stream_start_time": session.get("start_time"),
            "stream_duration": formatted_duration,
            "stream_remaining": formatted_remaining,
            "stream_eta": formatted_eta,
            "stream_video_resolution": session.get("stream_video_resolution"),
            "stream_container": session.get("stream_container"),
            "stream_bitrate": session.get("stream_bitrate"),
            "stream_video_bitrate": session.get("stream_video_bitrate"),
            "stream_video_codec": session.get("stream_video_codec"),
            "stream_video_framerate": session.get("stream_video_framerate"),
            "stream_video_full_resolution": session.get("stream_video_full_resolution"),
            "stream_video_dovi_profile": session.get("stream_video_dovi_profile"),
            "stream_video_decision": session.get("stream_video_decision"),
            "stream_audio_bitrate": session.get("stream_audio_bitrate"),
            "stream_audio_codec": session.get("stream_audio_codec"),
            "stream_audio_channels": session.get("stream_audio_channels"),
            "stream_audio_channel_layout": session.get("stream_audio_channel_layout"),
            "stream_audio_language": session.get("stream_audio_language"),
            "stream_audio_language_code": session.get("stream_audio_language_code"),
        })

        # ------------------------------------------------------
        # 2) PLEX ATTRIBUTES (if plex_enabled == True)
        # ------------------------------------------------------
        if plex_enabled and plex_token and plex_base_url:
            rating_key = session.get("rating_key")
            if rating_key:
                attributes["rating_key"] = session.get("rating_key")
            summary = session.get("summary", "")
            if summary:
                attributes["summary"] = summary
            contentRating = session.get("content_rating")
            if contentRating:
                attributes["content_rating"] = contentRating
            audienceRating = session.get("audience_rating")
            if audienceRating:
                attributes["audience_rating"] = audienceRating
            rating = session.get("rating")
            if rating:
                attributes["rating"] = rating
            attributes["library_folder"] = session.get("library_section_title")
            viewCount = session.get("view_count")
            if viewCount:
                attributes["view_count"] = viewCount
            lastViewedAt = session.get("last_viewed_at")    
            if lastViewedAt:
                last_viewed_timestamp = int(lastViewedAt)
                last_viewed_date = datetime.fromtimestamp(last_viewed_timestamp)
                attributes["last_viewed_at"] = last_viewed_date.strftime("%Y-%m-%d %H:%M:%S")
            attributes["in_credits"] = self._in_credits
            if self._credits_start_time:
                attributes["credits_start_time"] = self._credits_start_time



        return attributes



class TautulliDiagnosticSensor(CoordinatorEntity, SensorEntity):
    """
    Representation of a Tautulli diagnostic sensor,
    also using the sessions_coordinator to read 'diagnostics'.
    """

    def __init__(self, coordinator, entry, metric):
        """Initialize the diagnostic sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._metric = metric
        self._attr_unique_id = f"tautulli_{entry.entry_id}_{metric}"
        self.entity_id = f"sensor.tautulli_{metric}"
        self._attr_name = f"{metric.replace('_', ' ').title()}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = self.device_info
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_class = SensorDeviceClass.DATA_SIZE

        if metric in ["total_bandwidth", "lan_bandwidth", "wan_bandwidth"]:
            self._attr_native_unit_of_measurement = "Mbps"
        else:
            self._attr_native_unit_of_measurement = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_active_streams")},
            "name": f"{self._entry.title} Active Streams",
            "manufacturer": "Richardvaio",
            "model": "Tautulli Active Streams",
            "entry_type": "service",
        }

    @property
    def state(self):
        """Return the main diagnostic value from 'diagnostics'."""
        diagnostics = self.coordinator.data.get("diagnostics", {})
        raw_value = diagnostics.get(self._metric, 0)

        if self._metric in ["total_bandwidth", "lan_bandwidth", "wan_bandwidth"]:
            try:
                return round(float(raw_value) / 1000, 1)
            except Exception as err:
                _LOGGER.error("Error converting bandwidth: %s", err)
                return raw_value

        return raw_value

    @property
    def extra_state_attributes(self):
        """Return additional diagnostic attributes (e.g. session list)."""
        if self._metric != "stream_count":
            return {}
        sessions = self.coordinator.data.get("sessions", [])
        filtered_sessions = []
        for s in sessions:
            filtered_sessions.append({
                "username": (s.get("username") or "").lower(),
                "user": (s.get("user") or "").lower(),
                "full_title": s.get("full_title"),
                "stream_start_time": s.get("start_time"),
                "start_time_raw": s.get("start_time_raw"),
                "Stream_paused_duration_sec": s.get("Stream_paused_duration_sec"),
                "session_id": s.get("session_id"),
            })
        return {"sessions": filtered_sessions}

    @property
    def icon(self):
        icon_map = {
            "stream_count": "mdi:plex",
            "stream_count_direct_play": "mdi:play-circle",
            "stream_count_direct_stream": "mdi:play-network",
            "stream_count_transcode": "mdi:cog",
            "total_bandwidth": "mdi:download-network",
            "lan_bandwidth": "mdi:lan",
            "wan_bandwidth": "mdi:wan",
        }
        return icon_map.get(self._metric, "mdi:chart-bar")


class TautulliUserStatsSensor(CoordinatorEntity, SensorEntity):
    """
    One sensor per user, each with '_stats_' in its unique_id,
    referencing history_coordinator.data for user_stats.
    """

    def __init__(self, coordinator, entry: ConfigEntry, username: str, stats: dict, index: int):
        super().__init__(coordinator)
        self._entry = entry
        self._username = username
        self._stats = stats
        self._index = index

        # Must have "_stats_" so the removal code can detect it
        self._attr_unique_id = f"{entry.entry_id}_{username.lower()}_{index}_stats_"
        self._attr_name = f"{username} Stats"

        # Put these sensors under a separate device named "<Integration Title> Statistics"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_statistics_device")},
            "name": f"{entry.title} Statistics",
            "manufacturer": "Richardvaio",
            "model": "Tautulli Statistics",
        }

    @property
    def icon(self) -> str:
        return "mdi:account"
        
    @property
    def state(self):
        user_stats = self.coordinator.data["user_stats"].get(self._username, {})
        return user_stats.get("total_play_duration", "0h 0m")

    @property
    def extra_state_attributes(self):
        """Return watch-history stats from self._stats (parsed from get_history)."""
        return {
            # --- Basic Play Counts ---
            "total_plays": self._stats.get("total_plays", 0),
            "movie_plays": self._stats.get("movie_plays", 0),
            "tv_plays": self._stats.get("tv_plays", 0),

            # --- Duration & Completion & Pause Metrics ---
            "total_play_duration": self._stats.get("total_play_duration", "0h 0m"),
            "total_completion_rate": self._stats.get("total_completion_rate", 0.0),
            "longest_play": self._stats.get("longest_play", "0h 0m"),
            "average_play_gap": self._stats.get("average_play_gap", "N/A"),
            "paused_count": self._stats.get("paused_count", 0),
            "total_paused_duration": self._stats.get("total_paused_duration", "0h 0m"),

            # --- Popular Titles ---
            "most_popular_show": self._stats.get("most_popular_show", ""),
            "most_popular_movie": self._stats.get("most_popular_movie", ""),
            
            # --- Watch Times --- Weekday & Gaps ---
            "days_since_last_watch": self._stats.get("days_since_last_watch"),
            "preferred_watch_time": self._stats.get("preferred_watch_time", ""),
            "weekday_plays": self._stats.get("weekday_plays", []),
            "watched_morning": self._stats.get("watched_morning", 0),
            "watched_afternoon": self._stats.get("watched_afternoon", 0),
            "watched_midday": self._stats.get("watched_midday", 0),
            "watched_evening": self._stats.get("watched_evening", 0),
            
            # --- Transcode / Playback Types ---
            "transcode_count": self._stats.get("transcode_count", 0),
            "direct_play_count": self._stats.get("direct_play_count", 0),
            "direct_stream_count": self._stats.get("direct_stream_count", 0),
            "transcode_percentage": self._stats.get("transcode_percentage", 0.0),
            "common_transcode_devices": self._stats.get("common_transcode_devices", ""),
            "last_transcode_date": self._stats.get("last_transcode_date", ""),

            # --- Device Usage ---
            "most_used_device": self._stats.get("most_used_device", ""),
            "common_audio_language": self._stats.get("common_audio_language", "Unknown"),
            
            # --- Geo Location ---
            "geo_city": self._stats.get("geo_city"),
            "geo_region": self._stats.get("geo_region"),
            "geo_country": self._stats.get("geo_country"),
            "geo_code": self._stats.get("geo_code"),
            "geo_latitude": self._stats.get("geo_latitude"),
            "geo_longitude": self._stats.get("geo_longitude"),
            "geo_continent": self._stats.get("geo_continent"),
            "geo_postal_code": self._stats.get("geo_postal_code"),
            "geo_timezone": self._stats.get("geo_timezone"),

            # --- LAN vs WAN ---
            "lan_plays": self._stats.get("lan_plays", 0),
            "wan_plays": self._stats.get("wan_plays", 0),
        }

    async def async_update(self):
        """
        If the coordinator data changes, re-fetch this user's stats
        from history_coordinator.data["user_stats"] if needed.
        """
        all_stats = self.coordinator.data.get("user_stats", {})
        self._stats = all_stats.get(self._username, {})


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    This is called when the user changes options in the UI.
    If stats are disabled, remove existing stats sensors/device.
    Then reload the config entry so the updated sensor count or stats toggle
    can be applied to the sensor platform.
    """
    enable_stats = entry.options.get(CONF_ENABLE_STATISTICS, False)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    # If user turned stats off, remove all stats sensors & device
    if not enable_stats:
        for entity_entry in list(ent_reg.entities.values()):
            if (
                entity_entry.config_entry_id == entry.entry_id
                and "_stats_" in (entity_entry.unique_id or "")
            ):
                ent_reg.async_remove(entity_entry.entity_id)

        # remove the stats device
        for device_entry in list(dev_reg.devices.values()):
            if (
                entry.entry_id in device_entry.config_entries
                and any(
                    iden[0] == DOMAIN and iden[1] == f"{entry.entry_id}_statistics_device"
                    for iden in device_entry.identifiers
                )
            ):
                dev_reg.async_remove_device(device_entry.id)

    # Force a fresh Tautulli fetch (if your coordinator is sessions_coordinator):
    sessions_coordinator = hass.data[DOMAIN][entry.entry_id]["sessions_coordinator"]
    await sessions_coordinator.async_request_refresh()

    # Reload the config entry so the changes take effect
    await hass.config_entries.async_reload(entry.entry_id)