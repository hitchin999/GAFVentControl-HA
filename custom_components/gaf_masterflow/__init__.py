"""GAF MasterFlow Vent Control integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GafApiClient, GafApiError, GafAuthError
from .const import CONF_PASSWORD, CONF_USER_ROLE, CONF_USERNAME, DEFAULT_USER_ROLE, DOMAIN
from .coordinator import GafCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GAF MasterFlow from a config entry."""
    session = async_get_clientsession(hass)
    client = GafApiClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        user_role=entry.data.get(CONF_USER_ROLE, DEFAULT_USER_ROLE),
    )

    try:
        await client.async_login()
    except GafAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except GafApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = GafCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
