# ISS Track

A Home Assistant integration to track the International Space Station (ISS) in real time. Inspired by the European Space Agency's [ESA ISS Tracker](https://isstracker.spaceflight.esa.int/) — the map styling is the only element carried over; the implementation is entirely different, with the following features (* = differs from the ESA implementation):

## Features
- Displays the current position of the ISS on a world map with day/night shading and orbit paths (±1.5h).
- Shows live data including latitude, longitude, altitude, speed, and ISS time.
- Adds an "ISS Track" panel to the Home Assistant sidebar automatically — no manual dashboard setup. *
- Optimized for speed on load: instant map display and quick display of ISS position. *
- Defaults to imperial units, with a metric toggle. *
- Larger map display, 3x larger. *
- Fetches fresh ISS orbital elements (TLE) from Celestrak, with a 2-hour cache.
- Click the ISS icon to open a live video feed from the ISS (via YouTube).

## Installation

### HACS (recommended)
1. In HACS, add this repository as a custom repository (category: Integration), or install "ISS Track" if it is available in the HACS store.
2. Install **ISS Track** and restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **ISS Track**.
4. An "ISS Track" panel appears in the sidebar.

### Manual
1. Copy `custom_components/iss_track/` into `custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant, then add the integration under **Settings → Devices & Services**.

All frontend assets (map images, fonts, satellite.js, astronomy.browser.js) are served directly from the integration — nothing needs to be copied into `config/www/`.

## Usage
- Open the **ISS Track** panel from the sidebar to view the live map.
- Click on the ISS icon to view a live feed from the ISS (via YouTube).
- Use the Metric/Imperial toggle to switch units; the fullscreen button expands the map.

## Credits
- Uses [`satellite.js`](https://github.com/shashwatak/satellite-js) for orbital calculations.
- Uses [`astronomy.browser.js`](https://github.com/cosinekitty/astronomy) for moon position calculations.
- Orbital elements courtesy of [Celestrak](https://celestrak.org/).

## License
MIT License
