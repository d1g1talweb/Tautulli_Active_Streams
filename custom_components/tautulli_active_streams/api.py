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
        _LOGGER.debug("🔍 Fetching Tautulli activity: %s", url)

        try:
            async with self._session.get(url, timeout=10, ssl=self._verify_ssl) as response:
                status = response.status

                if status == 200:
                    try:
                        data = await response.json()
                    except Exception as json_err:
                        _LOGGER.warning("⚠️ Invalid JSON response from API: %s", json_err)
                        return {"sessions": [], "diagnostics": {}}

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

                else:
                    return {"sessions": [], "diagnostics": {}}

        except Exception as err:
            return {"sessions": [], "diagnostics": {}}
            
    async def terminate_session(self, session_id, message=""):
        url = f"{self._base_url}?apikey={self._api_key}&cmd=terminate_session"
        params = {
            "session_id": session_id,
            "message": message
        }
        _LOGGER.debug("Terminating Tautulli session: %s", params)
        async with self._session.get(url, params=params, timeout=10, ssl=self._verify_ssl) as resp:
            return await resp.json()
    

            
