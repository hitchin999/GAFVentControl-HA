"""Config flow for GAF MasterFlow Vent Control."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GafApiClient, GafApiError, GafAuthError
from .const import (
    CONF_PASSWORD,
    CONF_USER_ROLE,
    CONF_USERNAME,
    DEFAULT_USER_ROLE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_USER_ROLE, default=DEFAULT_USER_ROLE): vol.In(
            ["contractor", "consumer"]
        ),
    }
)


class GafConfigFlow(ConfigFlow, domain=DOMAIN):
    """Email + password login flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = GafApiClient(
                session=session,
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                user_role=user_input.get(CONF_USER_ROLE, DEFAULT_USER_ROLE),
            )
            try:
                await client.async_login()
            except GafAuthError as err:
                _LOGGER.warning("Auth failed: %s", err)
                errors["base"] = "invalid_auth"
            except GafApiError as err:
                _LOGGER.warning("Connection failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
