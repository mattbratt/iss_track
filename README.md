# ISS Track

A Home Assistant integration to track the International Space Station (ISS) in real-time.

## Features
- Displays the current position of the ISS on a world map.
- Shows live data including latitude, longitude, altitude, speed, and ISS time.
- Automatically creates a "Space" dashboard in Home Assistant with the ISS Tracker view.

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
- Images provided by [source of images, if applicable].

## License
MIT License