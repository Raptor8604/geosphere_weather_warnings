"""Constants for the Geosphere Weather Warnings integration."""

DOMAIN = "geosphere_weather_warnings"
ATTRIBUTION = "Data provided by GeoSphere Austria"

CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_WARNING_TYPE = "warning_type" # z.B. EVENT, ALPINE

DEFAULT_WARNING_TYPE = "EVENT" # Standard-Warnungstyp

API_ENDPOINT_COORDS = "https://warnapi.geosphere.at/v1/warnings/coords"
REQUEST_TIMEOUT = 10  # in seconds
SCAN_INTERVAL_MINUTES = 15 # Wie oft die Daten abgerufen werden sollen