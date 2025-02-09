import logging
import aiohttp
import asyncio

_LOGGER = logging.getLogger(__name__)

class TautulliAPI:
    """Handles communication with the Tautulli API."""

    def __init__(self, url, api_key, session, verify_ssl=True):
        """Initialize the API client."""
        self._url = url.rstrip("/") 
        self._api_key = api_key
        self._session = session
        self._verify_ssl = verify_ssl 

        self._base_url = f"{self._url}/api/v2"

    async def get_activity(self):
        """Retrieve active session data from Tautulli."""
        url = f"{self._base_url}?apikey={self._api_key}&cmd=get_activity"
    
        try:
            _LOGGER.debug("🔍 Fetching Tautulli activity: %s", url)
    
            async with self._session.get(url, timeout=10, ssl=self._verify_ssl) as response:
                status = response.status
    
                if status == 200:
                    try:
                        data = await response.json()
                        response_data = data.get("response", {}).get("data", {})
    
                        diagnostics = {
                            "stream_count": response_data.get("stream_count", 0),
                            "stream_count_direct_play": response_data.get("stream_count_direct_play", 0),
                            "stream_count_direct_stream": response_data.get("stream_count_direct_stream", 0),
                            "stream_count_transcode": response_data.get("stream_count_transcode", 0),
                            "total_bandwidth": response_data.get("total_bandwidth", 0),
                            "lan_bandwidth": response_data.get("lan_bandwidth", 0),
                            "wan_bandwidth": response_data.get("wan_bandwidth", 0),
                        }
    
                        return {"sessions": response_data.get("sessions", []), "diagnostics": diagnostics}
    
                    except Exception as json_err:
                        _LOGGER.warning("⚠️ Invalid JSON response from API: %s", json_err)
                        return {"sessions": [], "diagnostics": {}}
    
                elif status == 502:
                    _LOGGER.warning("⚠️ Tautulli might be down! Received 502 Bad Gateway.")
                    return {"sessions": [], "diagnostics": {}}
    
                else:
                    _LOGGER.warning("❌ API request failed! Status: %s | Response: %s", status, await response.text())
                    return {"sessions": [], "diagnostics": {}}
    
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.warning("🚨 API request failed due to connection issues.")
            return {"sessions": [], "diagnostics": {}}
