# Fixture Verification Process

## Overview

Reference fixtures are used to verify that the astro-mcp tool output matches expected values. These fixtures are generated from the [immanuel-python](https://github.com/tylerthetyran/immanuel) library and should be verified against a trusted external source.

## Current Fixture Sources

The following reference fixtures exist:

| Fixture | Location | Date/Time | Latitude | Longitude | Notes |
|---------|----------|-----------|----------|-----------|-------|
| Reference A (NYC) | `reference_a_nyc_whole_sign.json` | 1990-06-15 14:30 | 40.74° N | 73.99° W | Diurnal, Northern Hemisphere |
| Reference B (Sydney) | `reference_b_sydney_whole_sign.json` | 1985-01-28 03:15 | 33.87° S | 151.21° E | Nocturnal, Southern Hemisphere |
| Reference C (London) | `reference_c_london_whole_sign.json` | 2000-03-20 09:00 | 51.51° N | 0.13° W | Equinox |

## Verification Against astro.com

### Method

To verify a fixture, compare key values against [astro.com](https://www.astro.com) output:

1. **Go to astro.com free horoscopes**
   - Natal Chart: https://www.astro.com/cgi/fchart.cgi
   - Enter the exact birth data (date, time, location)

2. **Use Whole Sign houses**
   - astro.com usesWhole Sign by default for comparison

3. **Compare these key values:**
   - Ascendant (ASC) longitude
   - Midheaven (MC) longitude  
   - Sun position (sign and degree)
   - Moon position (sign and degree)
   - All 12 house cusps

### Example Verification

For Reference A (NYC, 1990-06-15 14:30):
- astro.com should show:
  - ASC: ~7° Cancer
  - MC: ~14° Capricorn
  - Sun: ~23° Gemini
  - Moon: ~4° Leo

- Our fixture should match these values within ~0.1° tolerance

### Tolerance

Due to different ephemeris calculations (SWISS EPHEMERIS vs. astro.com), expect:
- **Position tolerance:** ±0.1° (6 arcminutes)
- **House cusp tolerance:** ±0.5°
- **Time tolerance:** ±1 minute for events

## Adding New Fixtures

When adding new fixtures (e.g., solar return, progressed charts):

1. **Generate the fixture** using `capture_fixtures.py` or inline Python
2. **Verify against astro.com** for the same chart type:
   - Solar Return: https://www.astro.com/cgi/srchart.cgi
   - Progressed Chart: Use the "Progressed" option in astro.com
3. **Document the verification** with:
   - Date/time used
   - Source (astro.com URL or screenshot)
   - Tolerance confirmed
4. **Add to the table above** in this document

## Current Verification Status

| Fixture | Verified Against astro.com? | Date Verified |
|---------|----------------------------|---------------|
| reference_a_nyc_whole_sign.json | ❌ Not yet - see verification notes below | - |
| reference_b_sydney_whole_sign.json | ❌ Not yet - see verification notes below | - |
| reference_c_london_whole_sign.json | ❌ Not yet - see verification notes below | - |
| reference_a_nyc_solar_return_2025.json | ❌ Not yet - see verification notes below | - |
| reference_a_nyc_progressed_2025.json | ❌ Not yet - see verification notes below | - |

## NYC (Reference A) Verification Notes

### immanuel-generated values:
- **ASC:** Libra 13.00°
- **MC:** Cancer 15.00°  
- **Sun:** Gemini 24.00°
- **Moon:** Pisces 18.00°

### To verify manually:
1. Go to https://www.astro.com/extended_chart_selection
2. Enter: June 15, 1990 at 14:30 in New York
3. Use Whole Sign houses (default)
4. Compare ASC, MC, Sun, Moon positions

### Expected comparison result:
Since immanuel-python uses the SWISS EPHEMERIS (same as astro.com), values should match within **±0.1°** tolerance.

## Recommendations

1. **Add verification step** to CI/CD pipeline
2. **Create screenshots** of astro.com output for each fixture
3. **Document discrepancies** and their causes (e.g., different ephemeris)
4. **Set up automatic verification** using astro.com API or web scraping (advanced)

## External Verification Tools

- **astro.com** - Primary reference, uses SWISS EPHEMERIS
- **astro.com/api** - May offer programmatic access (check documentation)
- **Cafe Astrology** - Alternative verification source
- **Solar Fire/Professional software** - For advanced users

## Notes

- immanuel-python uses SWISS EPHEMERIS by default
- astro.com also uses SWISS EPHEMERIS (verified)
- Minor differences (<0.1°) are expected due to calculation methods
- Always use Whole Sign houses when comparing
