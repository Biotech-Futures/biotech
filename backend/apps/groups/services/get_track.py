from apps.groups.models import Tracks, Countries, CountryStates
from django.db import transaction

"""
Currently, the tracks system works based on whatever regions that BIOTech Futures Support.
In Australia, these consist of a Track for each state, denoted "AUS-<state_short_form>" e.g. "AUS-NSW", "AUS-QLD".
For any other country, regardless of the country's inherent state, it will just be the country.
The only other country supported is Brazil. This shall be denoted "BRA". Otherwise, it shall be named "GLO" for Global.

So, this function will be to get an arbitrary country and region name, and then figure out which Track the combination belongs to.
It should not create one, as we assume this will be created in another function, by an admin.
"""

# Exception hierarchy for explicit error signaling to API layer


class TrackResolutionError(Exception):
    """Base class for track resolution errors."""


class InvalidInputError(TrackResolutionError):
    pass


class CountryNotFoundError(TrackResolutionError):
    def __init__(self, country: str):
        super().__init__(f"Country '{country}' not found.")
        self.country = country


class StateNotFoundError(TrackResolutionError):
    def __init__(self, country: str, state: str):
        super().__init__(f"State '{state}' not found in country '{country}'.")
        self.country = country
        self.state = state


class TrackNotConfiguredError(TrackResolutionError):
    def __init__(self, track_name: str):
        super().__init__(f"No Track configured with name '{track_name}'.")
        self.track_name = track_name


def get_supported_track(country_name, region_name):
    '''
    Resolves and returns an existing Track based on BIOTech Futures reach.
    Australia: Track is 'AUS-<STATE_SHORT>'
    Brazil: Track is 'BRA'
    Global: Track is 'GLO'
    Args:
      country_name (str): country name
      region_name (str): state short form for AU; otherwise ignored
    Returns:
      Track (Track): The BIOTech track related to the given data
    Raises:
      InvalidInputError | CountryNotFoundError | StateNotFoundError | TrackNotConfiguredError
    '''
    country_raw = (country_name or "").strip()
    region_raw = (region_name or "").strip()
    if not country_raw:
        raise InvalidInputError("Country is required to resolve a Track.")

    country_t = country_raw.title()
    region_up = region_raw.upper()  # we expect short form for AU

    country = Countries.objects.filter(country_name__iexact=country_t).first()
    if not country:
        raise CountryNotFoundError(country_t)

    if country_t == "Australia":
        if not region_up:
            raise InvalidInputError(
                "Region (state short form) is required for Australia.")
        state_exists = CountryStates.objects.filter(
            country=country, state_name__iexact=region_up).exists()
        if not state_exists:
            raise StateNotFoundError(country_t, region_up)
        track_name = f"AUS-{region_up}"
    elif country_t == "Brazil":
        track_name = "BRA"
    else:
        track_name = "GLO"

    track = Tracks.objects.filter(track_name=track_name).first()
    if not track:
        raise TrackNotConfiguredError(track_name)
    return track
