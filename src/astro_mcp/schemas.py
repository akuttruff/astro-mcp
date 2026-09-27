"""Pydantic models for all tool parameters."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional


def get_coordinates_for_params(
    latitude: Optional[str | float],
    longitude: Optional[str | float],
    city: Optional[str],
    state: Optional[str] = None,
    country: Optional[str] = None
) -> tuple[float, float]:
    """
    Get coordinates from either provided values or geocoding.
    
    Args:
        latitude: Latitude string (if None, will use geocoding)
        longitude: Longitude string (if None, will use geocoding)
        city: City name for geocoding
        state: State/province (optional)
        country: Country (optional)
    
    Returns:
        Tuple of (latitude, longitude) as floats
    
    Raises:
        RuntimeError: If geocoding fails
    """
    from astro_mcp.utils import geocode_location
    
    if latitude is not None and longitude is not None:
        # Use provided coordinates
        lat_val = float(latitude)
        lon_val = float(longitude)
    elif city is not None:
        # Geocode the location
        lat_val, lon_val = geocode_location(city, state, country)
    else:
        raise ValueError("Must provide either coordinates or city/state/country")
    
    return lat_val, lon_val


class LocationParams(BaseModel):
    """Base model for location parameters with flexible input formats."""

    latitude: Optional[str] = Field(
        default=None,
        description="Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south."
    )
    longitude: Optional[str] = Field(
        default=None,
        description="Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g., '118w15'). Negative or 'w' for west."
    )

    # Optional location components for geocoding
    city: Optional[str] = Field(
        default=None,
        description="City name. If provided with state/country, will be geocoded to coordinates."
    )
    state: Optional[str] = Field(
        default=None,
        description="State/province code or name (e.g., 'NY' or 'New York'). Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country code or name (e.g., 'US' or 'United States'). Optional."
    )

    @model_validator(mode='after')
    def validate_location_input(self):
        """Validate that either coordinates OR city/state/country are provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_location = self.city is not None

        if not has_coords and not has_location:
            raise ValueError(
                "Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self


class NatalChartParams(BaseModel):
    """Parameters for creating a natal chart."""

    date_time: str = Field(
        ...,
        description="Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace."
    )
    house_system: Optional[str] = Field(
        None,
        description="House system to use. Default: 'whole_sign'. See list_house_systems for options."
    )
    time_is_dst: Optional[bool] = Field(
        None,
        description="Set true/false to clarify if the time is Daylight Saving Time."
    )
    timezone_offset: Optional[float] = Field(
        None,
        description="Explicit UTC offset in hours (e.g. -8.0 for PST, -7.0 for PDT)."
    )

    # Location can be specified either as coordinates OR city/state/country
    latitude: Optional[str] = Field(
        default=None,
        description="Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south."
    )
    longitude: Optional[str] = Field(
        default=None,
        description="Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west."
    )

    # Optional location components for geocoding
    city: Optional[str] = Field(
        default=None,
        description="City name. If provided with state/country, will be geocoded to coordinates."
    )
    state: Optional[str] = Field(
        default=None,
        description="State/province code or name (e.g., 'NY' or 'New York'). Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country code or name (e.g., 'US' or 'United States'). Optional."
    )

    @model_validator(mode='after')
    def validate_location_input(self):
        """Validate that either coordinates OR city/state/country are provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_location = self.city is not None

        if not has_coords and not has_location:
            raise ValueError(
                "Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self


class SolarReturnParams(BaseModel):
    """Parameters for creating a solar return chart."""

    date_time: str = Field(
        ...,
        description="Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace."
    )
    year: int = Field(
        ...,
        description="The year for the solar return (e.g., 2025). Must be between 1200 and 4649."
    )
    house_system: Optional[str] = Field(
        None,
        description="House system to use. Default: 'whole_sign'. See list_house_systems for options."
    )

    latitude: Optional[str] = Field(
        default=None,
        description="Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south."
    )
    longitude: Optional[str] = Field(
        default=None,
        description="Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west."
    )

    city: Optional[str] = Field(
        default=None,
        description="City name. If provided with state/country, will be geocoded to coordinates."
    )
    state: Optional[str] = Field(
        default=None,
        description="State/province code or name (e.g., 'NY' or 'New York'). Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country code or name (e.g., 'US' or 'United States'). Optional."
    )

    @model_validator(mode='after')
    def validate_location_input(self):
        """Validate that either coordinates OR city/state/country are provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_location = self.city is not None

        if not has_coords and not has_location:
            raise ValueError(
                "Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self


class ProgressedParams(BaseModel):
    """Parameters for creating a progressed chart."""

    date_time: str = Field(
        ...,
        description="Birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. Local time at the birthplace."
    )
    target_date: str = Field(
        ...,
        description="The date to progress to, in format 'YYYY-MM-DD'."
    )
    house_system: Optional[str] = Field(
        None,
        description="House system to use. Default: 'whole_sign'. See list_house_systems for options."
    )

    latitude: Optional[str] = Field(
        default=None,
        description="Latitude. Decimal degrees (e.g. '34.05') or DMS (e.g. '34n03'). Negative or 's' for south."
    )
    longitude: Optional[str] = Field(
        default=None,
        description="Longitude. Decimal degrees (e.g. '-118.24') or DMS (e.g. '118w15'). Negative or 'w' for west."
    )

    city: Optional[str] = Field(
        default=None,
        description="City name. If provided with state/country, will be geocoded to coordinates."
    )
    state: Optional[str] = Field(
        default=None,
        description="State/province code or name (e.g., 'NY' or 'New York'). Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country code or name (e.g., 'US' or 'United States'). Optional."
    )

    @model_validator(mode='after')
    def validate_location_input(self):
        """Validate that either coordinates OR city/state/country are provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_location = self.city is not None

        if not has_coords and not has_location:
            raise ValueError(
                "Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self


class TransitParams(BaseModel):
    """Parameters for creating a transit chart."""

    date_time: str = Field(
        ...,
        description="Birth date and time of the natal chart being transited. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'."
    )
    house_system: Optional[str] = Field(
        None,
        description="House system to use. Default: 'whole_sign'. See list_house_systems for options."
    )

    latitude: Optional[str] = Field(
        default=None,
        description="Latitude of the natal chart location. Decimal degrees (e.g. '34.05') or DMS."
    )
    longitude: Optional[str] = Field(
        default=None,
        description="Longitude of the natal chart location. Decimal degrees (e.g. '-118.24') or DMS."
    )

    city: Optional[str] = Field(
        default=None,
        description="City name for natal location. If provided with state/country, will be geocoded to coordinates."
    )
    state: Optional[str] = Field(
        default=None,
        description="State/province code or name. Optional."
    )
    country: Optional[str] = Field(
        default=None,
        description="Country code or name. Optional."
    )

    transit_date_time: Optional[str] = Field(
        None,
        description="The date/time of the transit. Format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'. If omitted, uses current time. For lunation work, specify the exact time of a new or full moon."
    )

    @model_validator(mode='after')
    def validate_location_input(self):
        """Validate that either coordinates OR city/state/country are provided."""
        has_coords = self.latitude is not None and self.longitude is not None
        has_location = self.city is not None

        if not has_coords and not has_location:
            raise ValueError(
                "Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self


class SynastryParams(BaseModel):
    """Parameters for creating a synastry (composite) chart."""

    # Person A
    date_time_a: str = Field(
        ...,
        description="Person A birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'."
    )

    latitude_a: Optional[str] = Field(
        default=None,
        description="Person A latitude. Decimal degrees (e.g. '34.05') or DMS."
    )
    longitude_a: Optional[str] = Field(
        default=None,
        description="Person A longitude. Decimal degrees (e.g. '-118.24') or DMS."
    )

    city_a: Optional[str] = Field(
        default=None,
        description="Person A city name. If provided with state/country, will be geocoded to coordinates."
    )
    state_a: Optional[str] = Field(
        default=None,
        description="Person A state/province code or name. Optional."
    )
    country_a: Optional[str] = Field(
        default=None,
        description="Person A country code or name. Optional."
    )

    # Person B
    date_time_b: str = Field(
        ...,
        description="Person B birth date and time in format 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DDTHH:MM'."
    )

    latitude_b: Optional[str] = Field(
        default=None,
        description="Person B latitude. Decimal degrees (e.g. '34.05') or DMS."
    )
    longitude_b: Optional[str] = Field(
        default=None,
        description="Person B longitude. Decimal degrees (e.g. '-118.24') or DMS."
    )

    city_b: Optional[str] = Field(
        default=None,
        description="Person B city name. If provided with state/country, will be geocoded to coordinates."
    )
    state_b: Optional[str] = Field(
        default=None,
        description="Person B state/province code or name. Optional."
    )
    country_b: Optional[str] = Field(
        default=None,
        description="Person B country code or name. Optional."
    )

    house_system: Optional[str] = Field(
        None,
        description="House system to use. Default: 'whole_sign'. See list_house_systems for options."
    )

    @model_validator(mode='after')
    def validate_location_inputs(self):
        """Validate that either coordinates OR city/state/country are provided for each person."""
        # Validate Person A
        has_coords_a = self.latitude_a is not None and self.longitude_a is not None
        has_location_a = self.city_a is not None

        if not has_coords_a and not has_location_a:
            raise ValueError(
                "Person A: Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        # Validate Person B
        has_coords_b = self.latitude_b is not None and self.longitude_b is not None
        has_location_b = self.city_b is not None

        if not has_coords_b and not has_location_b:
            raise ValueError(
                "Person B: Must provide either (latitude AND longitude) OR (city, state, country)"
            )

        return self
