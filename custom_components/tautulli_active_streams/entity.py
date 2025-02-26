from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, LOGGER

class TautulliEntity(CoordinatorEntity, Entity):
    """Defines a base Tautulli Active Streams entity."""

    _attr_has_entity_name = True
    _attr_available = True
     
    def __init__(self, coordinator, entry):
        """Initialize the Tautulli entity."""
        super().__init__(coordinator)
        self.entry = entry
        self.coordinator = coordinator
        self._attr_available = True

    async def async_update(self) -> None:
        """Update Tautulli entity."""
        if not self.enabled:
            return

        try:
            await self.coordinator.async_request_refresh()
            self._attr_available = True
        except Exception as err:
            if self._attr_available:
                LOGGER.debug(f"An error occurred while updating Tautulli entity: {err}")
            self._attr_available = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Tautulli instance."""
        host = self.entry.data.get(CONF_HOST)
        port = self.entry.data.get(CONF_PORT)

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{host}:{port}")},
            manufacturer="Tautulli",
            name="Tautulli Active Streams",
            configuration_url=f"http://{host}:{port}"
        )
