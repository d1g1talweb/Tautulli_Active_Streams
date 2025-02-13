import logging
import aiohttp
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

class TautulliImageView(HomeAssistantView):
    """Handle image proxy requests for Tautulli."""
    url = "/api/tautulli/image"
    name = "api:tautulli:image"
    requires_auth = False  # Set to True if you need authentication

    async def get(self, request):
        """Proxy image requests."""
        hass = request.app["hass"]

        # Extract query parameters from the URL
        img = request.query.get("img")
        width = request.query.get("width", "300")
        height = request.query.get("height", "450")
        fallback = request.query.get("fallback", "poster")
        refresh = request.query.get("refresh", "true")

        if not img:
            return web.Response(status=400, text="Missing image parameter")

        # Retrieve integration configuration data from hass.data.
        # You need to store this data during setup.
        config_data = hass.data.get("tautulli_integration_config")
        if not config_data:
            return web.Response(status=500, text="Tautulli configuration not found")

        base_url = config_data.get("base_url")
        api_key = config_data.get("api_key")
        if not base_url or not api_key:
            return web.Response(status=500, text="Tautulli base URL or API key missing")

        # Build the Tautulli image URL using the configuration and query parameters.
        tautulli_image_url = (
            f"{base_url}/api/v2?apikey={api_key}&cmd=pms_image_proxy"
            f"&img={img}&width={width}&height={height}"
            f"&fallback={fallback}&refresh={refresh}"
        )

        _LOGGER.debug("Fetching image from: %s", tautulli_image_url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(tautulli_image_url) as response:
                    if response.status != 200:
                        _LOGGER.error("Error fetching image, status: %s", response.status)
                        return web.Response(status=response.status, text="Error fetching image")
                    image_data = await response.read()
                    # You might need to adjust the content type based on the image format.
                    return web.Response(body=image_data, content_type="image/jpeg")
        except Exception as err:
            _LOGGER.exception("Exception fetching image: %s", err)
            return web.Response(status=500, text="Error fetching image")
