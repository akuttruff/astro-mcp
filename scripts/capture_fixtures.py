#!/usr/bin/env python3
"""Script to capture reference fixtures from immanuel for testing.

This script generates verified JSON output from immanuel that can be used
as fixtures for MCP tool testing. Each fixture should be manually verified
against astro.com before committing.
"""

import json
from datetime import datetime

from immanuel import charts


# Reference test data points
REFERENCE_DATA = [
    {
        "label": "Reference A (NYC)",
        "date_time": "1990-06-15 14:30",
        "latitude": 40.74,
        "longitude": -73.99,
    },
    {
        "label": "Reference B (Sydney)",
        "date_time": "1985-01-28 03:15",
        "latitude": -33.87,
        "longitude": 151.21,
    },
    {
        "label": "Reference C (London)",
        "date_time": "2000-03-20 09:00",
        "latitude": 51.51,
        "longitude": -0.13,
    },
]


def capture_natal_fixture(data, house_system="whole_sign"):
    """Capture a natal chart fixture."""
    native = charts.Subject(
        date_time=data["date_time"].replace("T", " "),
        latitude=data["latitude"],
        longitude=data["longitude"],
    )
    
    config = charts.Config()
    # House system should be set as integer
    from immanuel.const import chart as chart_const
    if house_system == "whole_sign":
        config.house_system = chart_const.WHOLE_SIGN
    elif house_system == "placidus":
        config.house_system = chart_const.PLACIDUS
    else:
        config.house_system = getattr(chart_const, house_system.upper(), chart_const.WHOLE_SIGN)
    
    natal = charts.Natal(native, config=config)
    
    # Serialize to JSON
    json_str = json.dumps(natal, cls=charts.ToJSON, indent=2)
    
    return json_str


def main():
    """Generate all fixtures."""
    print("Generating reference fixtures...")
    
    for ref in REFERENCE_DATA:
        print(f"\n{'='*60}")
        print(f"Capturing: {ref['label']}")
        print(f"{'='*60}")
        
        fixture = capture_natal_fixture(ref)
        
        # Create a safe filename
        label_safe = ref["label"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        filename = f"tests/fixtures/{label_safe}_whole_sign.json"
        
        with open(filename, "w") as f:
            f.write(fixture)
        
        print(f"Saved: {filename}")
        
        # Print a summary
        data = json.loads(fixture)
        print(f"  Objects: {len(data.get('objects', {}))}")
        print(f"  Houses: {len(data.get('houses', {}))}")
        print(f"  Aspects: {len(data.get('aspects', []))}")


if __name__ == "__main__":
    main()
