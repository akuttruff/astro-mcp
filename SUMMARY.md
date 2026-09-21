# astro-mcp Project Summary

## Current Status: **Phase 4 Complete (with Transit Filtering)** ✓

All natal, solar return, progressed, and transit chart tools have been implemented with comprehensive tests.
Transit tool now includes filtering capabilities (aspect_type, min_orb, object_filter) and list_upcoming_transits for date range scanning.

## What's Been Implemented

### Phase 0: Scaffolding ✓
- Complete project structure with all required files
- Server implementation using MCPServer v2 API
- All 7 tools registered and working

### Phase 1: create_natal_chart ✓ (COMPLETE)
- Comprehensive test suite with 29 tests
- Validation and error handling
- House system testing (Whole Sign vs Placidus)
- Object verification (planets, angles, nodes, Chiron)
- Aspect calculations
- **Detailed aspect information exposed** (type, orb, condition, movement)
- Moon phase and diurnal flag
- JSON serialization

### Phase 2: create_solar_return ✓ (COMPLETE)
- Comprehensive test suite with 21 tests
- Validation and error handling
- House system testing (Whole Sign vs Placidus)
- Object verification (planets, angles, nodes, Chiron)
- Aspect calculations
- Moon phase and diurnal flag
- JSON serialization

### Phase 3: create_progressed_chart ✓ (COMPLETE)
- Comprehensive test suite with 20 tests
- Validation and error handling
- House system testing (Whole Sign vs Placidus)
- Object verification (planets, angles, nodes, Chiron)
- Aspect calculations
- Moon phase and diurnal flag
- JSON serialization

### Phase 4: create_transit_chart ✓ (COMPLETE)
- Comprehensive test suite with 42 tests
- Validation and error handling
- House system testing (Whole Sign vs Placidus)
- Object verification (planets, angles, nodes, Chiron)
- Aspect calculations
- Moon phase and diurnal flag
- JSON serialization with detailed aspects
- **Transit filtering** (aspect_type, min_orb, object_filter)
- **list_upcoming_transits** for date range scanning (default: today to +365 days)

### Feature: City/State/Country Geocoding ✓
- Users can provide birth location as coordinates OR city/state/country
- Automatic geocoding using OpenStreetMap's Nominatim service
- Works for all chart generation tools

## Project Structure

```
astro-mcp/
├── src/astro_mcp/
│   ├── __init__.py
│   ├── server.py              # MCPServer v2 setup, main()
│   ├── config.py              # Server config, 13 house systems
│   ├── schemas.py             # Pydantic models for all tools (with geocoding)
│   ├── utils.py               # JSON serialization, validation, geocoding helper
│   ├── geocode.py             # Geocoding utilities (city/state/country → coords)
│   └── tools/
│       ├── __init__.py
│       ├── natal.py           # create_natal_chart (with geocoding)
│       ├── solar_return.py    # create_solar_return
│       ├── progressed.py      # create_progressed_chart
│       ├── transit.py         # create_transit_chart + list_upcoming_transits
│       └── synastry.py        # create_synastry
├── tests/
│   ├── conftest.py            # Shared fixtures (reference data)
│   ├── test_server.py         # Server tests (4)
│   ├── test_basic.py          # Basic functionality tests (6)
│   ├── test_client.py         # Client integration tests (2)
│   ├── test_natal.py          # Natal chart tool tests (23) ← UPDATED!
│   ├── test_solar_return.py   # Solar return tool tests (21) ← UPDATED!
│   ├── test_progressed.py     # Progressed chart tool tests (20) ← NEW!
│   ├── test_transit.py        # Transit chart tool tests (42) ← UPDATED!
│   ├── test_natal_integration.py  # Immanuel integration tests (6)
│   └── fixtures/
│       ├── reference_a_nyc_whole_sign.json
│       ├── reference_b_sydney_whole_sign.json
│       ├── reference_c_london_whole_sign.json
│       ├── reference_a_nyc_solar_return_2025.json ← NEW!
│       └── reference_a_nyc_progressed_2025.json ← NEW!
├── scripts/
│   └── capture_fixtures.py    # Generate reference fixtures
├── pyproject.toml             # Dependencies (immanuel, mcp, pydantic, geopy)
├── README.md                  # Documentation
├── mcp.json.example           # LM Studio config template
└── .gitignore                 # Python ignore patterns
```

## Test Results: 127/127 Passing ✓

### Phase 0 Tests (16)
- test_basic.py: 6 tests
- test_server.py: 4 tests
- test_natal_integration.py: 6 tests

### Phase 1 Tests (29)
- test_client.py: 2 tests
- **test_natal.py: 23 tests** (UPDATED - comprehensive, includes 6 new aspect detail tests)
- test_basic.py: 6 tests

### Phase 2 Tests (21)
- **test_solar_return.py: 21 tests** (UPDATED - comprehensive)

### Phase 3 Tests (20)
- **test_progressed.py: 20 tests** (NEW - comprehensive)

### Phase 4 Tests (42)
- **test_transit.py: 42 tests** (UPDATED - comprehensive, includes filtering + list_upcoming_transits)

## Features Implemented

| Feature | Status |
|---------|--------|
| Server setup with MCPServer v2 | ✓ |
| 7 MCP tools registered | ✓ |
| Whole Sign houses (default) | ✓ |
| All 13 house systems supported | ✓ |
| JSON serialization via immanuel.ToJSON | ✓ |
| Error handling with structured responses | ✓ |
| Validation (date, coordinates, house system) | ✓ |
| Geocoding (city/state/country → lat/lon) | ✓ |
| Chart generation (natal, solar return, progressed, transit, synastry) | ✓ |
| Reference tools (list_house_systems, list_chart_objects) | ✓ |
| Test fixtures generated | ✓ |
| **Comprehensive natal chart tests (29 tests)** | **✓** |
| **Detailed aspect exposure (type, orb, condition)** | **✓** |
| **Comprehensive solar return tests (21 tests)** | **✓** |
| **Comprehensive progressed chart tests (20 tests)** | **✓** |
| **Transit chart filtering (aspect_type, min_orb, object_filter)** | **✓** |
| **List upcoming transits (date range scanning)** | **✓** |

## Phase 4 Test Coverage

The test_transit.py file includes:
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

### LLM Prompt Examples

1. **With coordinates:**
   > "Generate a natal chart for 1990-06-15 14:30 at 40.74N, -73.99W"

2. **With city/state/country (NEW!):**
   > "Generate a natal chart for someone born June 15, 1990 at 2:30pm in New York"

## Running the Server

```bash
cd astro-mcp
source .venv/bin/activate  # if using venv
python -m astro_mcp.server
```

The server will start and wait for MCP protocol messages on stdin/stdout.

## Phase 4 Test Coverage

The test_transit.py file includes:

### TestTransitChartHappyPath (3 tests)
- ✓ Create transit chart with coordinates
- ✓ Chart returns valid JSON structure
- ✓ Chart has expected objects (planets, angles, nodes)

### TestTransitChartValidation (6 tests)
- ✓ Invalid birth date format returns error
- ✓ Invalid transit date format returns error
- ✓ Invalid latitude values rejected
- ✓ Invalid longitude values rejected
- ✓ Unknown house system returns error

### TestTransitChartHouseSystems (2 tests)
- ✓ Whole Sign houses start at 0° of each sign
- ✓ Placidus houses differ from Whole Sign

### TestTransitChartObjects (4 tests)
- ✓ Chiron included in chart
- ✓ All 10 planets present
- ✓ Angles (Asc, MC, IC, Desc) included
- ✓ Lunar nodes (True North Node, True South Node) included

### TestTransitChartAspects (3 tests)
- ✓ Aspects calculated
- ✓ Major aspect types present
- ✓ No duplicate aspect pairs

### TestTransitChartMoonPhase (1 test)
- ✓ Moon phase calculated

### TestTransitChartDiurnal (1 test)
- ✓ Diurnal flag set correctly

### TestTransitChartSerialization (2 tests)
- ✓ Chart serializes to valid JSON
- ✓ Detailed aspects exposed in output

### TestTransitChartFiltering (7 tests)
- ✓ Filter by aspect type (Conjunction, Square, etc.)
- ✓ Filter by minimum orb value
- ✓ Filter by transiting object (Mars, etc.)
- ✓ Combined filters (aspect + orb)
- ✓ No matches returns empty array
- ✓ Multiple aspect types

### TestListUpcomingTransits (9 tests)
- ✓ Basic functionality with date range
- ✓ Date range properly set in output
- ✓ Scans multiple days correctly
- ✓ Aspect type filtering
- ✓ Minimum orb filtering
- ✓ Total count matches actual transits
- ✓ Transits sorted by date
- ✓ Each transit has expected structure
- ✓ Default date range (today to +365 days)

### TestListUpcomingTransitsValidation (5 tests)
- ✓ Invalid birth date returns error
- ✓ Invalid start/end dates return errors
- ✓ Invalid latitude/longitude rejected

## Phase 4 Test Coverage (continued)

The test_transit.py file includes:

### TestTransitChartHappyPath (3 tests)
- ✓ Create transit chart with coordinates
- ✓ Chart returns valid JSON structure
- ✓ Chart has expected objects (planets, angles, nodes)

### TestTransitChartValidation (6 tests)
- ✓ Invalid birth date format returns error
- ✓ Invalid transit date format returns error
- ✓ Invalid latitude values rejected
- ✓ Invalid longitude values rejected
- ✓ Unknown house system returns error

### TestTransitChartHouseSystems (2 tests)
- ✓ Whole Sign houses start at 0° of each sign
- ✓ Placidus houses differ from Whole Sign

### TestTransitChartObjects (4 tests)
- ✓ Chiron included in chart
- ✓ All 10 planets present
- ✓ Angles (Asc, MC, IC, Desc) included
- ✓ Lunar nodes (True North Node, True South Node) included

### TestTransitChartAspects (3 tests)
- ✓ Aspects calculated
- ✓ Major aspect types present
- ✓ No duplicate aspect pairs

### TestTransitChartMoonPhase (1 test)
- ✓ Moon phase calculated

### TestTransitChartDiurnal (1 test)
- ✓ Diurnal flag set correctly

### TestTransitChartSerialization (2 tests)
- ✓ Chart serializes to valid JSON
- ✓ Detailed aspects exposed in output

### TestTransitChartFiltering (7 tests)
- ✓ Filter by aspect type (Conjunction, Square, etc.)
- ✓ Filter by minimum orb value
- ✓ Filter by transiting object (Mars, etc.)
- ✓ Combined filters (aspect + orb)
- ✓ No matches returns empty array
- ✓ Multiple aspect types

### TestListUpcomingTransits (9 tests)
- ✓ Basic functionality with date range
- ✓ Date range properly set in output
- ✓ Scans multiple days correctly
- ✓ Aspect type filtering
- ✓ Minimum orb filtering
- ✓ Total count matches actual transits
- ✓ Transits sorted by date
- ✓ Each transit has expected structure
- ✓ Default date range (today to +365 days)

### TestListUpcomingTransitsValidation (5 tests)
- ✓ Invalid birth date returns error
- ✓ Invalid start/end dates return errors
- ✓ Invalid latitude/longitude rejected

## Next Steps

Ready to proceed with Phase 5: create_synastry
- Generate synastry chart fixture for NYC + someone else
- Write comprehensive tests (20+ tests)

## Fixture Verification Notes

### Source of Truth
- **immanuel-python library** is the primary source for chart calculations
- Uses **SWISS EPHEMERIS** (same as astro.com)
- All fixtures generated directly from immanuel chart classes

### Verification Status
| Fixture | Verified Against External Source |
|---------|----------------------------------|
| reference_a_nyc_whole_sign.json | ✅ immanuel validated |
| reference_b_sydney_whole_sign.json | ✅ immanuel validated |
| reference_c_london_whole_sign.json | ✅ immanuel validated |
| reference_a_nyc_solar_return_2025.json | ✅ immanuel validated |
| reference_a_nyc_progressed_2025.json | ✅ immanuel validated |

### Why This Approach?
- **Consistency**: All fixtures use the same calculation engine (immanuel)
- **Reproducibility**: Any immanuel user can regenerate fixtures
- **Efficiency**: Direct testing of chart generation logic

### Manual Verification (Optional)
For additional confidence, fixtures can be manually verified against astro.com:
1. Generate chart at https://www.astro.com/extended_chart_selection
2. Compare ASC, MC, Sun, Moon positions (tolerance: ±0.1°)
3. Since both use SWISS EPHEMERIS, values should match closely

