"""The Geosphere Weather Warnings integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Geosphere Weather Warnings component."""
    # Hier wird sichergestellt, dass der DOMAIN-Speicher im hass.data existiert
    hass.data.setdefault(DOMAIN, {})

    # Wir verwenden die Home-Koordinaten, wenn keine spezifischen angegeben sind
    # Für diese erste Version nutzen wir immer die Home-Koordinaten.
    # Eine Erweiterung könnte die Konfiguration über configuration.yaml ermöglichen.
    _LOGGER.info("Geosphere Weather Warnings integration is being set up using Home Assistant's home coordinates.")

    # Lade die Sensor-Plattform
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            "sensor",
            DOMAIN,
            {
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude
            }, # Hier werden die Home-Koordinaten übergeben
            config
        )
    )
    return True