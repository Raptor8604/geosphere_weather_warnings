"""Sensor platform for Geosphere Weather Warnings."""
import logging
from datetime import timedelta, datetime
import asyncio

import aiohttp
from async_timeout import timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)

from .const import (
    DOMAIN,
    ATTRIBUTION,
    API_ENDPOINT_COORDS,
    CONF_WARNING_TYPE,
    DEFAULT_WARNING_TYPE,
    REQUEST_TIMEOUT,
    SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

# Definiere das Scan-Intervall
SCAN_INTERVAL = timedelta(minutes=SCAN_INTERVAL_MINUTES)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    if discovery_info is None:
        _LOGGER.error("Geosphere Weather Warnings sensor requires discovery_info.")
        return

    latitude = discovery_info.get(CONF_LATITUDE, hass.config.latitude)
    longitude = discovery_info.get(CONF_LONGITUDE, hass.config.longitude)
    # Holen den Warnungstyp aus der Konfiguration oder verwenden den Standardwert
    # Für diese erste Version ist der Typ im Code festgelegt, könnte aber über config_flow konfigurierbar gemacht werden.
    warning_type = DEFAULT_WARNING_TYPE

    coordinator = GeosphereWarningCoordinator(hass, latitude, longitude, warning_type)
    await coordinator.async_config_entry_first_refresh() # Erster Datenabruf

    async_add_entities([GeosphereWeatherWarningSensor(coordinator)], True)


class GeosphereWarningCoordinator(DataUpdateCoordinator):
    """Coordinates fetching data from the Geosphere API."""

    def __init__(self, hass, latitude, longitude, warning_type):
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.warning_type = warning_type
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    # Vorschlag für die _async_update_data Methode in GeosphereWarningCoordinator
async def _async_update_data(self):
    """Fetch data from API endpoint."""
    params = {
        "lat": str(self.latitude),
        "lon": str(self.longitude),
        "type": self.warning_type,
    }
    try:
        async with timeout(REQUEST_TIMEOUT):
            response = await self.session.get(API_ENDPOINT_COORDS, params=params)
            response.raise_for_status()
            data = await response.json()
            _LOGGER.debug("Data fetched from Geosphere API: %s", data)

        active_warnings = []
        # Prüfe, ob es sich um eine FeatureCollection handelt und der "features"-Schlüssel vorhanden ist
        if data and data.get("type") == "FeatureCollection" and "features" in data:
            now = datetime.utcnow() # API-Zeiten sind vermutlich in UTC

            for feature in data.get("features", []): # Iteriere über das "features"-Array
                warn_props = feature.get("properties") # Das "properties"-Objekt ist das WarningObject

                if not warn_props:
                    _LOGGER.debug("Feature without properties skipped: %s", feature)
                    continue

                start_time_ms = warn_props.get("start")
                end_time_ms = warn_props.get("end")

                if start_time_ms and end_time_ms:
                    try:
                        start_dt = datetime.utcfromtimestamp(start_time_ms / 1000.0)
                        end_dt = datetime.utcfromtimestamp(end_time_ms / 1000.0)

                        if start_dt <= now <= end_dt:
                            active_warnings.append(warn_props) # Füge das WarningObject hinzu
                        else:
                            _LOGGER.debug(
                                "Warning '%s' skipped: not currently active (now: %s, start: %s, end: %s)",
                                warn_props.get("headline"), now, start_dt, end_dt
                            )
                    except ValueError as e:
                        _LOGGER.error("Error converting timestamp for warning '%s': %s", warn_props.get("headline"), e)
                else:
                    _LOGGER.warning(
                        "Warning '%s' without start/end time, including it by default. Review if this is desired.",
                        warn_props.get("headline")
                    )
                    active_warnings.append(warn_props) # Warnungen ohne Zeitangabe standardmäßig hinzufügen

        # Wenn 'data' nicht die erwartete Struktur hat, wird active_warnings leer sein oder nur die oben behandelten Fälle enthalten.
        # Du könntest hier noch ein _LOGGER.warning hinzufügen, wenn data keine FeatureCollection ist oder keine Features hat.
        elif data: # Falls 'data' existiert, aber nicht die erwartete Struktur hat
             _LOGGER.warning("Unexpected data structure received from Geosphere API: %s", data)


        return {"active_warnings": active_warnings, "raw_data": data}

    except aiohttp.ClientError as err:
        raise UpdateFailed(f"Error communicating with API: {err}") from err
    except asyncio.TimeoutError:
        raise UpdateFailed("Timeout communicating with API")
    except Exception as err: # Breitere Ausnahmebehandlung für unerwartete Fehler
        _LOGGER.exception("Unexpected error fetching Geosphere data")
        raise UpdateFailed(f"Unexpected error: {err}") from err


class GeosphereWeatherWarningSensor(SensorEntity):
    """Representation of a Geosphere Weather Warning sensor."""

    def __init__(self, coordinator: GeosphereWarningCoordinator):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"geosphere_warnings_{coordinator.latitude}_{coordinator.longitude}"
        self._attr_name = "Geosphere Weather Warnings"
        self._attr_icon = "mdi:alert-outline" # oder mdi:alert-circle-outline
        self._attr_attribution = ATTRIBUTION

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator handles updates."""
        return False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update the entity. Only used by the generic entity update service."""
        await self.coordinator.async_request_refresh()


    @property
    def state(self):
        """Return the state of the sensor (number of active warnings)."""
        if self.coordinator.data and "active_warnings" in self.coordinator.data:
            return len(self.coordinator.data["active_warnings"])
        return 0

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        if self.coordinator.data and "active_warnings" in self.coordinator.data:
            warnings_data = self.coordinator.data["active_warnings"]
            attrs["warnings"] = []
            for idx, warn_props in enumerate(warnings_data):
                attrs["warnings"].append(
                    {
                        "id": warn_props.get("id"),
                        "headline": warn_props.get("headline"),
                        "description": warn_props.get("description"),
                        "instruction": warn_props.get("instruction"),
                        "type": warn_props.get("type"),
                        "type_name": warn_props.get("typeName"),
                        "severity": warn_props.get("severity"),
                        "severity_name": warn_props.get("severityName"),
                        "urgency": warn_props.get("urgency"),
                        "certainty": warn_props.get("certainty"),
                        "start_time": datetime.utcfromtimestamp(warn_props.get("start") / 1000.0).isoformat() if warn_props.get("start") else None,
                        "end_time": datetime.utcfromtimestamp(warn_props.get("end") / 1000.0).isoformat() if warn_props.get("end") else None,
                        "altitude_start": warn_props.get("altitudeStart"),
                        "altitude_end": warn_props.get("altitudeEnd"),
                        "raw_data": warn_props # Enthält alle Felder
                    }
                )
            # Füge auch die rohen API-Daten hinzu, falls für Debugging nützlich
            # attrs["raw_api_response"] = self.coordinator.data.get("raw_data")
        return attrs