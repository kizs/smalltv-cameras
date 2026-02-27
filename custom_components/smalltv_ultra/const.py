"""Constants for SmallTV Ultra integration."""

DOMAIN = "smalltv_ultra"

CONF_HOST = "host"
CONF_CAMERAS = "cameras"
CONF_REFRESH_INTERVAL = "refresh_interval"
CONF_CYCLE_INTERVAL = "cycle_interval"
CONF_MODE = "mode"

DEFAULT_REFRESH_INTERVAL = 300  # seconds
DEFAULT_CYCLE_INTERVAL = 1      # seconds
DEFAULT_MODE = "cameras"

MODE_CAMERAS = "cameras"
MODE_BUILTIN = "builtin"

PLATFORMS = ["light", "number", "button", "select"]
