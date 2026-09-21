# Geocoding Feature

## Overview

The astro-mcp server now supports flexible location input. Users can provide birth location in two ways:

### Option 1: Coordinates (Traditional)
```json
{
  "date_time": "1990-06-15 14:30",
  "latitude": "40.74",
  "longitude": "-73.99"
}
```

### Option 2: City/State/Country (New!)
```json
{
  "date_time": "1990-06-15 14:30",
  "city": "New York",
  "state": "NY",      // Optional
  "country": "USA"    // Optional
}
```

## Implementation Details

### New Files Created:
1. **`src/astro_mcp/geocode.py`** - Geocoding utilities using geopy
2. **Updated `src/astro_mcp/schemas.py`** - Added city/state/country fields to all param models
3. **Updated `src/astro_mcp/utils.py`** - Added geocoding helper functions
4. **Updated `src/astro_mcp/tools/natal.py`** - Uses geocoding when city is provided

### New Dependencies:
- **geopy>=2.4** - For Nominatim geocoding service

## How It Works

1. User provides either coordinates OR city/state/country
2. If city is provided, the system calls `geocode_location()` 
3. Uses Nominatim (OpenStreetMap's geocoding service) to convert city → coordinates
4. Coordinates are validated before chart generation

## Example Usage in LM Studio

When asking the LLM to generate a natal chart, you can now say:

> "Generate my natal chart for someone born June 15, 1990 at 2:30pm in New York City"

The LLM will call `create_natal_chart` with:
```json
{
  "date_time": "1990-06-15 14:30",
  "city": "New York",
  "state": "NY",
  "country": "USA"
}
```

And the server will automatically geocode to coordinates before generating the chart.

## Geocoding Examples

| Input | Result |
|-------|--------|
| `city="New York", state="NY"` | (40.7128, -74.0060) |
| `city="Sydney", state="NSW"` | (-33.8688, 151.2093) |
| `city="London"` | (51.5074, -0.1278) |
| `city="Tokyo"` | (35.6762, 139.6503) |
| `city="Paris", country="France"` | (48.8566, 2.3522) |

## Error Handling

If geocoding fails, the user gets a clear error:
```json
{
  "error": "Geocoding failed",
  "detail": "Could not find coordinates for: Tokyo, Japan"
}
```

Or if geopy is not installed:
```json
{
  "error": "Geocoding failed",
  "detail": "Geocoding requires the 'geopy' package. Install it with: pip install geopy"
}
```

## Testing

Run these commands to verify geocoding works:

```bash
# Test geocoding directly
python -c "from astro_mcp.geocode import geocode_location; print(geocode_location('Paris', 'France'))"

# Test schema validation
python -c "from astro_mcp.schemas import NatalChartParams; p = NatalChartParams(date_time='1990-06-15 14:30', city='Paris'); print(p)"

# Run full test suite
pytest -v
```

## Notes

- Geocoding uses OpenStreetMap's Nominatim service (free, no API key required)
- The user agent is set to "astro-mcp-geo-1.0" for service identification
- Geocoding is optional - users can always provide coordinates directly if they prefer
