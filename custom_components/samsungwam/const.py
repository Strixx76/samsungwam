"""Constants for the Samsung Wireless Audio integration."""

import logging


LOGGER = logging.getLogger(__package__)


DOMAIN = "samsungwam"

ID_MAPPINGS = "media_player_entity_ids"
COORDINATOR = "wam_coordinator"

# Interval to check speaker connection in minutes
PING_INTERVAL = 10
# Min time in minutes between reconnection attempts
MIN_RECONNECTION_INTERVAL = 5
