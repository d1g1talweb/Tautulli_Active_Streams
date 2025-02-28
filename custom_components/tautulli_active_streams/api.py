import logging
import aiohttp
import asyncio

_LOGGER = logging.getLogger(__name__)

class TautulliAPI:
    """Handles communication with the Tautulli API."""
    def __init__(self, url, api_key, session, verify_ssl=True, timeout=10):
        """
        Initialize the API client.

        :param url: Base URL of your Tautulli instance.
        :param api_key: Your Tautulli API key.
        :param session: An aiohttp ClientSession (provided by Home Assistant).
        :param verify_ssl: Whether to verify SSL certificates.
        :param timeout: Request timeout in seconds (default 10).
        """
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._session = session
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._base_url = f"{self._url}/api/v2"

    async def _call_tautulli(self, cmd, params=None, method="GET"):
        """
        Generic helper to call any Tautulli API command.

        :param cmd: The Tautulli command, e.g. "get_activity" or "terminate_session".
        :param params: Dictionary of extra parameters for the Tautulli command.
        :param method: "GET" or "POST", default is "GET".
        :return: Parsed JSON response from Tautulli (or {} if an error occurs).
        """
        if params is None:
            params = {}

        url = f"{self._base_url}?apikey={self._api_key}&cmd={cmd}"
        method = method.upper()

        _LOGGER.debug("TautulliAPI: calling cmd=%s method=%s url=%s params=%s",
                      cmd, method, url, params)

        try:
            if method == "POST":
                # Some Tautulli commands might require POST in the future
                async with self._session.post(
                    url,
                    data=params,
                    timeout=self._timeout,
                    ssl=self._verify_ssl
                ) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except Exception as json_err:
                            _LOGGER.warning("Invalid JSON from Tautulli: %s", json_err)
                            return {}
                    else:
                        _LOGGER.warning("Non-200 status from Tautulli POST: %s", response.status)
                        return {}
            else:
                # Default to GET
                async with self._session.get(
                    url,
                    params=params,
                    timeout=self._timeout,
                    ssl=self._verify_ssl
                ) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except Exception as json_err:
                            _LOGGER.warning("Invalid JSON from Tautulli: %s", json_err)
                            return {}
                    else:
                        _LOGGER.warning("Non-200 status from Tautulli GET: %s", response.status)
                        return {}
        except asyncio.TimeoutError:
            _LOGGER.warning("Tautulli API request to %s timed out after %s seconds.", url, self._timeout)
            return {}
        except Exception as err:
            _LOGGER.error("Exception calling Tautulli %s: %s", cmd, err)
            return {}

    async def get_activity(self):
        """
        Retrieve active session data from Tautulli.

        :return: A dict with "sessions" and "diagnostics".
                 e.g. {"sessions": [...], "diagnostics": {...}}
        """
        resp = await self._call_tautulli("get_activity", method="GET")
        if not resp:
            return {"sessions": [], "diagnostics": {}}

        response_data = resp.get("response", {}).get("data", {})

        diagnostics = {
            "stream_count": response_data.get("stream_count", 0),
            "stream_count_direct_play": response_data.get("stream_count_direct_play", 0),
            "stream_count_direct_stream": response_data.get("stream_count_direct_stream", 0),
            "stream_count_transcode": response_data.get("stream_count_transcode", 0),
            "total_bandwidth": response_data.get("total_bandwidth", 0),
            "lan_bandwidth": response_data.get("lan_bandwidth", 0),
            "wan_bandwidth": response_data.get("wan_bandwidth", 0),
        }
        return {
            "sessions": response_data.get("sessions", []),
            "diagnostics": diagnostics,
        }

    async def terminate_session(self, session_id, message=""):
        """
        Terminate an active session via Tautulli's 'terminate_session' command.

        :param session_id: The Tautulli session ID to kill.
        :param message: An optional message to display to the user being killed.
        :return: Tautulli's response as a dict (or {} on error).
        """
        params = {"session_id": session_id, "message": message}
        # For terminate_session, Tautulli typically expects a GET. Adjust if needed.
        resp = await self._call_tautulli("terminate_session", params=params, method="GET")
        return resp
