import logging
import aiohttp
import asyncio

_LOGGER = logging.getLogger(__name__)

class TautulliAPI:
    """Handles communication with the Tautulli API."""

    def __init__(self, host, port, api_key, session):
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._api_key = api_key
        self._base_url = f"http://{host}:{port}/api/v2"
        self._session = session

    async def get_activity(self):
        """Retrieve active session data from Tautulli."""
        url = f"{self._base_url}?apikey={self._api_key}&cmd=get_activity"
        
        try:
            _LOGGER.debug("🔍 Fetching Tautulli activity: %s", url)  # Logs the full URL for debugging

            async with self._session.get(url, timeout=10) as response:
                if response.status != 200:
                    _LOGGER.error("❌ API request failed! Status: %s | Response: %s", response.status, await response.text())
                    return None
                
                try:
                    data = await response.json()
                except Exception as json_err:
                    _LOGGER.error("⚠️ API response is not valid JSON: %s", json_err)
                    return None
                
                return data.get("response", {}).get("data", {})

        except asyncio.TimeoutError:
            _LOGGER.error("⏳ Tautulli API request timed out!")
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error("🚨 API request failed: %s", err)
            return None