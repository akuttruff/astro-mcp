# astro-mcp

An MCP (Model Context Protocol) server that exposes the [immanuel-python](https://github.com/tylerthetyran/immanuel) v1.6.0 astrology calculation library as tools callable from local LLMs.

## Features

- **Natal charts** - Complete birth chart with planets, houses, aspects, and patterns
- **Solar return charts** - Annual forecast based on Sun's return to natal position
- **Progressed charts** - Secondary progression using "1 day = 1 year" method
- **Transit charts** - Track current planetary positions against a natal chart
- **Synastry/Composite charts** - Analyze relationships between two people
- **House system support** - 13 house systems including Whole Sign, Placidus, Equal, Koch, Campanus, Regiomontanus, Porphyry, Morinus, Polich Page, Alcabitus, Azimuthal, Meridian, and Vehlow Equal
- **Planetary hours** - The day's ruler and its 24 unequal hours from local sunrise and sunset, and the hour in effect now
- **Void-of-course Moon** - Each period from the Moon's last major aspect in a sign until she changes sign, and whether she is void now (traditional seven planets, or including the outer planets)
- **Lunations and eclipses** - New and full moons and solar and lunar eclipses in a date range, with exact local times and degrees; optionally the natal house and contacts of each in a birth chart
- **Reference tools** - List available house systems and chart objects
- **Flexible location input** - Provide birth location as coordinates (lat/lon) OR city/state/country with automatic geocoding

## Requirements

- Python 3.10 or higher
- LM Studio ≥ 0.3.17 (for MCP integration)
- Optional: `geopy` package for city/state/country geocoding (installed automatically)

## Installation

```bash
git clone https://github.com/yourusername/astro-mcp.git
cd astro-mcp
pip install -e ".[dev]"
```

The `geopy` package will be installed automatically for location geocoding.

## Usage

### Standalone Server

Run the server directly (it will hang waiting for MCP protocol on stdin/stdout):

```bash
python -m astro_mcp.server
```

### LM Studio Integration

1. Add the server to your `mcp.json` file:

**macOS/Linux:** `~/.lmstudio/mcp.json`
**Windows:** `%USERPROFILE%/.lmstudio/mcp.json`

```json
{
  "mcpServers": {
    "astro": {
      "command": "python",
      "args": ["-m", "astro_mcp.server"],
      "env": {}
    }
  }
}
```

2. Restart LM Studio or reload the MCP configuration
3. The astrological tools will be available in the Program tab

## Location Input

You can provide birth location in two ways:

### Option 1: Coordinates (Decimal Degrees or DMS)
```json
{
  "date_time": "1990-06-15 14:30",
  "latitude": "40.74",
  "longitude": "-73.99"
}
```

### Option 2: City/State/Country (Automatic Geocoding)
```json
{
  "date_time": "1990-06-15 14:30",
  "city": "New York",
  "state": "NY",
  "country": "USA"
}
```

Both formats work for all chart generation tools.

## Tools

### Chart Generation Tools

| Tool | Description |
|------|-------------|
| `create_natal_chart` | Generate a complete birth chart |
| `create_solar_return` | Generate an annual solar return forecast |
| `create_progressed_chart` | Generate a progressed chart for any date |
| `create_transit_chart` | Track current transits against a natal chart |
| `list_upcoming_transits` | List dated upcoming transits over a date range - against a birth chart, or as-is without one |
| `create_synastry` | Generate composite and cross-aspect charts for two people |

### Reference Tools

| Tool | Description |
|------|-------------|
| `list_house_systems` | Get available house systems with descriptions |
| `list_chart_objects` | List celestial objects included in charts |

## Example Output

The chart tools return a compact, structured JSON object (kept small so it
isn't truncated by MCP clients) containing:

- `chart_type` and `date_time`
- `house_system` used
- **`objects`** - Planets (Sun through Pluto), angles (Asc, MC, IC, Desc),
  lunar nodes, Chiron, and Arabic parts, keyed by name, each with a decimal
  `longitude`, a DMS `position` (e.g. `26°15'39" Virgo`), `house`, and planet
  `speed` (negative speed = retrograde)
- **`houses`** - 12 house cusps, each with a decimal `cusp` and DMS `position`
- **`aspects`** - Detailed aspects with type, orb, condition, and movement
- **`aspect_patterns`** - T-squares, grand trines, etc., named by object
- `moon_phase` and `diurnal` flag

Transit charts additionally place transiting objects in the natal chart's
houses and report the filtered transit-to-natal aspects. Solar return and
progressed charts include their specific date/time fields.

## Testing

Run the test suite:

```bash
pytest -v
```

Integration tests verify that immanuel generates correct charts.

## Development

The project follows a TDD approach with reference fixtures generated from verified astro.com data. Each tool has dedicated tests.

### Project Structure

```
astro-mcp/
├── src/astro_mcp/
│   ├── __init__.py
│   ├── server.py          # MCP server setup and registration
│   ├── config.py          # Server configuration
│   ├── schemas.py         # Pydantic models for tool parameters
│   ├── utils.py           # JSON serialization and validation utilities
│   ├── geocode.py         # Geocoding utilities (city/state/country to coords)
│   └── tools/
│       ├── __init__.py
│       ├── natal.py       # create_natal_chart tool
│       ├── solar_return.py # create_solar_return tool
│       ├── progressed.py  # create_progressed_chart tool
│       ├── transit.py     # create_transit_chart tool
│       └── synastry.py    # create_synastry tool
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_server.py     # Server integration tests
│   ├── test_basic.py      # Basic functionality tests
│   ├── test_natal_integration.py  # Chart generation tests
│   └── fixtures/          # Reference JSON fixtures
└── scripts/
    └── capture_fixtures.py  # Generate reference fixtures
```

## License

MIT License
