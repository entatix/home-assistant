"""
Support for Yamaha Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.yamaha/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY_MEDIA, SUPPORT_PAUSE, SUPPORT_STOP,
    SUPPORT_NEXT_TRACK, SUPPORT_PREVIOUS_TRACK,
    MEDIA_TYPE_MUSIC,
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (CONF_NAME, CONF_HOST, STATE_OFF, STATE_ON,
                                 STATE_PLAYING, STATE_IDLE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['rxv==0.3.0']

_LOGGER = logging.getLogger(__name__)

SUPPORT_YAMAHA = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
                 SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | \
                 SUPPORT_PLAY_MEDIA

# Only supported by some sources
SUPPORT_PLAYBACK = SUPPORT_PLAY_MEDIA | SUPPORT_PAUSE | SUPPORT_STOP | \
                   SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK

CONF_SOURCE_NAMES = 'source_names'
CONF_SOURCE_IGNORE = 'source_ignore'
CONF_ZONE_IGNORE = 'zone_ignore'

DEFAULT_NAME = 'Yamaha Receiver'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_SOURCE_IGNORE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_ZONE_IGNORE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SOURCE_NAMES, default={}): {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yamaha platform."""
    import rxv

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    source_ignore = config.get(CONF_SOURCE_IGNORE)
    source_names = config.get(CONF_SOURCE_NAMES)
    zone_ignore = config.get(CONF_ZONE_IGNORE)

    if discovery_info is not None:
        name = discovery_info[0]
        model = discovery_info[1]
        ctrl_url = discovery_info[2]
        desc_url = discovery_info[3]
        receivers = rxv.RXV(
            ctrl_url,
            model_name=model,
            friendly_name=name,
            unit_desc_url=desc_url).zone_controllers()
        _LOGGER.info("Receivers: %s", receivers)
    elif host is None:
        receivers = []
        for recv in rxv.find():
            receivers.extend(recv.zone_controllers())
    else:
        ctrl_url = "http://{}:80/YamahaRemoteControl/ctrl".format(host)
        receivers = rxv.RXV(ctrl_url, name).zone_controllers()

    for receiver in receivers:
        if receiver.zone not in zone_ignore:
            add_devices([
                YamahaDevice(name, receiver, source_ignore, source_names)])


class YamahaDevice(MediaPlayerDevice):
    """Representation of a Yamaha device."""

    def __init__(self, name, receiver, source_ignore, source_names):
        """Initialize the Yamaha Receiver."""
        self._receiver = receiver
        self._muted = False
        self._volume = 0
        self._pwstate = STATE_OFF
        self._current_source = None
        self._source_list = None
        self._source_ignore = source_ignore or []
        self._source_names = source_names or {}
        self._reverse_mapping = None
        self._is_playback_supported = False
        self._play_status = None
        self.update()
        self._name = name
        self._zone = receiver.zone

    def update(self):
        """Get the latest details from the device."""
        self._play_status = self._receiver.play_status()
        if self._receiver.on:
            if self._play_status is None:
                self._pwstate = STATE_ON
            elif self._play_status.playing:
                self._pwstate = STATE_PLAYING
            else:
                self._pwstate = STATE_IDLE
        else:
            self._pwstate = STATE_OFF

        self._muted = self._receiver.mute
        self._volume = (self._receiver.volume / 100) + 1

        if self.source_list is None:
            self.build_source_list()

        current_source = self._receiver.input
        self._current_source = self._source_names.get(
            current_source, current_source)
        self._is_playback_supported = self._receiver.is_playback_supported(
            self._current_source)

    def build_source_list(self):
        """Build the source list."""
        self._reverse_mapping = {alias: source for source, alias in
                                 self._source_names.items()}

        self._source_list = sorted(
            self._source_names.get(source, source) for source in
            self._receiver.inputs()
            if source not in self._source_ignore)

    @property
    def name(self):
        """Return the name of the device."""
        name = self._name
        if self._zone != "Main_Zone":
            # Zone will be one of Main_Zone, Zone_2, Zone_3
            name += " " + self._zone.replace('_', ' ')
        return name

    @property
    def state(self):
        """Return the state of the device."""
        return self._pwstate

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def source(self):
        """Return the current input source."""
        return self._current_source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        supported_commands = SUPPORT_YAMAHA
        if self._is_playback_supported:
            supported_commands |= SUPPORT_PLAYBACK
        return supported_commands

    def turn_off(self):
        """Turn off media player."""
        self._receiver.on = False

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        receiver_vol = 100 - (volume * 100)
        negative_receiver_vol = -receiver_vol
        self._receiver.volume = negative_receiver_vol

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._receiver.mute = mute

    def turn_on(self):
        """Turn the media player on."""
        self._receiver.on = True
        self._volume = (self._receiver.volume / 100) + 1

    def media_play(self):
        """Send play commmand."""
        self._call_playback_function(self._receiver.play, "play")

    def media_pause(self):
        """Send pause command."""
        self._call_playback_function(self._receiver.pause, "pause")

    def media_stop(self):
        """Send stop command."""
        self._call_playback_function(self._receiver.stop, "stop")

    def media_previous_track(self):
        """Send previous track command."""
        self._call_playback_function(self._receiver.previous, "previous track")

    def media_next_track(self):
        """Send next track command."""
        self._call_playback_function(self._receiver.next, "next track")

    def _call_playback_function(self, function, function_text):
        import rxv
        try:
            function()
        except rxv.exceptions.ResponseException:
            _LOGGER.warning(
                'Failed to execute %s on %s', function_text, self._name)

    def select_source(self, source):
        """Select input source."""
        self._receiver.input = self._reverse_mapping.get(source, source)

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from an ID.

        This exposes a pass through for various input sources in the
        Yamaha to direct play certain kinds of media. media_type is
        treated as the input type that we are setting, and media id is
        specific to it.
        """
        if media_type == "NET RADIO":
            self._receiver.net_radio(media_id)

    @property
    def media_artist(self):
        """Artist of current playing media."""
        if self._play_status is not None:
            return self._play_status.artist

    @property
    def media_album_name(self):
        """Album of current playing media."""
        if self._play_status is not None:
            return self._play_status.album

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        # Loose assumption that if playback is supported, we are playing music
        if self._is_playback_supported:
            return MEDIA_TYPE_MUSIC
        return None

    @property
    def media_title(self):
        """Artist of current playing media."""
        if self._play_status is not None:
            song = self._play_status.song
            station = self._play_status.station

            # If both song and station is available, print both, otherwise
            # just the one we have.
            if song and station:
                return '{}: {}'.format(station, song)
            else:
                return song or station
