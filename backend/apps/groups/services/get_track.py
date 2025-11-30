from apps.groups.models import Tracks, Countries, CountryStates
from django.db import transaction
from django.db.models import Q
from typing import Optional

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


def get_supported_track(country_name: str, region_name: str) -> Optional[Tracks]:
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
        # Accept either full state name (e.g., "New South Wales") or short form (e.g., "NSW")
        region_official_name = region_raw.lower().title()
        state = CountryStates.objects.filter(country=country).filter(
            Q(state_name__iexact=region_official_name) |
            Q(state_name__iexact=region_up) |
            Q(state_name_SHORT_FORM__iexact=region_up)
        ).first()
        if not state:
            raise StateNotFoundError(country_t, region_raw)
        short = (state.state_name_SHORT_FORM or "").strip().upper() or region_up
        track_name = f"AUS-{short}"
    elif country_t == "Brazil":
        track_name = "BRA"
    else:
        track_name = "GLO"

    track = Tracks.objects.filter(track_name=track_name).first()
    if not track:
        raise TrackNotConfiguredError(track_name)
    return track

def get_supported_countryState(country_name: str, region_name: str) -> Optional[CountryStates]:
    """
    Resolves and returns an existing CountryState (state) for a given country and region.
    Args:
      country_name (str): country name, full or short
      region_name (str): region name, full state or short form
    Returns:
      region (CountryStates): The supported CountryStates objects, or raises error
    Raises:
    InvalidInputError | CountryNotFoundError | StateNotFoundError
    """
    country = get_supported_country(country_name)
    region_raw = (region_name or "").strip()
    if not region_raw:
        raise InvalidInputError("Region is required")
    
    region_official_name = region_raw.lower().title()
    region_short = region_raw.upper()

    state = CountryStates.objects.filter(country=country).filter(
        Q(state_name__iexact=region_short) |
        Q(state_name__iexact=region_official_name) |
        Q(state_name_SHORT_FORM__iexact=region_short)
    ).first()
    if not state:
        raise StateNotFoundError(country.country_name, region_raw)
    return state

def get_supported_country(country_name: str) -> Optional[Countries]:
    """
    Resolves and returns an existing, supported country, regardless if searched through short or long form
    Args:
      country_name (str): country name, full or short e.g. Australia, AUSTRALIA, australia, Aus, aus, AUS,
    Returns:
      Country (Countries): The supported Countries object, or raises an error
    Raises:
      InvalidInputError | CountryNotFoundError
    """
    country_raw = (country_name or "").strip()
    if not country_raw:
        raise InvalidInputError("Country is required")
    country_official_name = country_raw.lower().title()
    country_short = country_raw.upper()
    country = Countries.objects.filter(
        Q(country_name__iexact=country_official_name) |
        Q(country_name_SHORT_FORM__iexact=country_short)
    ).first()
    if not country:
        raise CountryNotFoundError(country_raw)
    return country


    