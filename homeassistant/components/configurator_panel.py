import asyncio
from collections import defaultdict
from datetime import timedelta
from itertools import groupby
import voluptuous as vol
from homeassistant.const import HTTP_BAD_REQUEST
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components import recorder, script
from homeassistant.components.frontend import register_built_in_panel
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_HIDDEN
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.history import get_unique_states
import requests

DOMAIN = 'history'
DEPENDENCIES = ['recorder', 'http']

CONF_EXCLUDE = 'exclude'
CONF_INCLUDE = 'include'
CONF_ENTITIES = 'entities'
CONF_DOMAINS = 'domains'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        CONF_EXCLUDE: vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        }),
        CONF_INCLUDE: vol.Schema({
            vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
            vol.Optional(CONF_DOMAINS, default=[]):
                vol.All(cv.ensure_list, [cv.string])
        })
    }),
}, extra=vol.ALLOW_EXTRA)

SIGNIFICANT_DOMAINS = ('thermostat', 'climate')
IGNORE_DOMAINS = ('zone', 'scene',)


def setup(hass, config):
    """Setup the panel hooks."""
    hass.http.register_view(UniqueStatesView(hass))



    return True

def get_known_states(hass, entity_id=None, api_url='state', api_password=''):
    """Return the last 5 states for entity_id."""
    html = requests.get('http://home.gelb.fish:8123/api/{}/{}'.format(api_url, entity_id),
                        headers={'X-HA-access': api_password})
    result = {}
    if entity_id is not None:
        entity_state = hass.states.get(entity_id)
        entity_domain = entity_state.domain
        if entity_domain == 'climate':
            result = {'operation_mode': entity_state['operation_list'],
                      'swing_mode': entity_state['swing_list']}

        if entity_domain == 'light':
            result = {'state': ['ON', 'OFF']}
    else:
        result = get_unique_states(hass, entity_id=entity_id)
    return result


class UniqueStatesView(HomeAssistantView):
    """Handle unique states view requests."""

    url = '/api/history/entity/{entity_id}/config-panel'
    name = 'api:history:config-panel'

    def __init__(self, hass):
        """Initilalize the history unique states view."""
        super().__init__(hass)
        self.hass = hass

    def wrapper_func(self, entity_id):
        states = get_known_states(hass=self.hass, entity_id=entity_id, api_password='qwerty')
        return states

    @asyncio.coroutine
    def get(self, request, entity_id):
        """Retrieve unique states of entity."""
        result = yield from self.hass.loop.run_in_executor(
            None, self.wrapper_func, entity_id)
        return self.json(result)