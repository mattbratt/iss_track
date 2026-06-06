# ISS Track

A Home Assistant integration to track the International Space Station (ISS) in real-time. Inspired by the European Space Agenncy's (ESA) "ESA ISS Tracker" (https://isstracker.spaceflight.esa.int/), I wanted to improve on it in serveral ways. I loved the way the graphics displayed on the map, and so that is the only item this is used from the ESA solution, the map. The code implemented here is totally different and has the following features (* = features that differ from the ESA implementation) 

## Features
- Displays the current position of the ISS on a world map.
- Shows live data including latitude, longitude, altitude, speed, and ISS time.
- Automatically creates a "Space" dashboard in Home Assistant with the ISS Tracker view *
- Optimized for speed on load. Instant map display, and quick display of ISS position *
- Defaults to imperial rather than metric *
- Larger map display, 3 x larger *
- Uses  `astronomy.browser.js` for moon position calculations.

## Installation
1. Copy the `iss_track` folder to `custom_components/` in your Home Assistant configuration directory.
2. Restart Home Assistant.
3. A new dashboard named "ISS Track" will be automatically created. You can access it from the sidebar.

## Usage
- Navigate to the "ISS Track" dashboard in Home Assistant to view the ISS Tracker.
- Click on the ISS icon to view a live feed from the ISS (via YouTube).

## Credits
- Uses `satellite.js` for orbital calculations.
- Uses `astronomy.browser.js` for moon position calculations.

## License
MIT License
