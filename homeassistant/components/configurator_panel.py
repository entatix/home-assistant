import asyncio
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.history import get_unique_states
import requests
import logging
from homeassistant.helpers.entity_component import EntityComponent

DEPENDENCIES = ['http', 'history']
DOMAIN = 'frontend'

def setup(hass, config):
    """Setup the panel hooks."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass)

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

    url = '/api/config-panel'
    name = 'api:config-panel'

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
        result = self.hass.loop.run_in_executor(
            None, self.wrapper_func, entity_id)
        #return self.json(result)
        return self.json({'stuff': 'things'})
