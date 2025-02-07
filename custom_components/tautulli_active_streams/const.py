import logging  # ✅ Fix: Import loggi

DOMAIN = "tautulli_active_streams"
DEFAULT_SCAN_INTERVAL = 10  # Default to 10 seconds
DEFAULT_SESSION_COUNT = 5   # Default to 5 sensors
LOGGER = logging.getLogger(__package__)  # ✅ Fix: Add this line
