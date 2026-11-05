# ISS Track

A Home Assistant integration that tracks the International Space Station (ISS) in real time and tells you when you can see it from where you are.

New in version 2: visible pass predictions, entities, a calendar, a dashboard card and a pass-alert blueprint. See the [changelog](CHANGELOG.md).

<img width="1000" height="573" alt="image" src="https://github.com/user-attachments/assets/f7c90b72-0945-48d1-91d4-f0ad0052eda1" />


## Features
- Displays the current position of the ISS on a world map with day/night shading and orbit paths (1.5 hours ahead and behind).
- Shows live data including latitude, longitude, altitude, speed, and ISS time.
- Adds an "ISS Track" panel to the Home Assistant sidebar automatically, with no manual dashboard setup.
- Predicts the passes you can actually see: the station in sunlight, your sky dark, and the station at least 10° up.
- Rates each pass (Poor, Fair, Good, Excellent) and estimates its brightness, and lets you choose which ones count.
- Works for your home location, for the device you are holding, and optionally for chosen people.
- Exposes everything as entities, a calendar and a dashboard card, so automations can act on a pass.
- Optional sky forecast from any weather entity, so alerts can skip a cloudy pass.
- Imperial or metric units, with a toggle on the map.
- Fetches fresh ISS orbital elements (TLE) from Celestrak every 2 hours and keeps the last good set if Celestrak cannot be reached.
- Click the ISS icon to open a live video feed from the ISS (via YouTube).

## Installation

Requires Home Assistant 2024.12 or newer.

1. Open **Settings > Marketplace**. Search for **ISS Track**, or add `https://github.com/mattbratt/iss_track` as a custom repository of type Integration.
2. Download **ISS Track** and restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and search for **ISS Track**.
4. An "ISS Track" panel appears in the sidebar.

The Marketplace is built into Home Assistant from 2026.11. On older versions, do steps 1 and 2 in HACS instead.

All frontend assets (map images, fonts, the panel and the card) are served directly from the integration, so nothing needs to be copied into `config/www/`. The one Python dependency (`sgp4`, for the orbit calculation) is installed by Home Assistant.

## Usage
- Open the **ISS Track** panel from the sidebar to view the live map.
- Click on the ISS icon to view a live feed from the ISS (via YouTube).
- Use the Metric/Imperial toggle to switch units; the fullscreen button expands the map.
- Under the map, **Visible passes** lists every pass you can see in the next 10 days. The blue ring on the map is where the station has to be for you to see it, and the next matching pass is drawn in green.
- Switch between **Home** and **This device** to choose whose sky the passes are for.
- The gear opens **Pass settings**.

## Pass settings

One set of settings decides which passes count. The panel, the dashboard card, the calendar and the entities all use it. Change it from the gear in the panel (administrators only) or from **Settings > Devices & Services > ISS Track > Configure**.

| Setting | Default | What it does |
|---|---|---|
| Pass quality | Good and Excellent | Judged on the highest point reached while the station is visible |
| Minimum brightness | Magnitude -2 or brighter | Leaves out fainter passes. Lower is brighter |
| Time of day | Evening only | About half of all visible passes are before dawn |
| Weather entity | None | Where the sky forecast for each pass comes from |
| Alert when the sky is | Partly cloudy or better | Used by alerts and the card. A pass with no forecast yet is never skipped |
| People | None | Gives each chosen person their own pass entities |
| Position update interval | 30 seconds | How often the live position entities update |

Pass quality bands:

| Quality | Highest point | Typical experience |
|---|---|---|
| Poor | 10-20° | Easy to miss; dim, hazy, often obstructed |
| Fair | 21-40° | Visible if you know where to look |
| Good | 41-60° | Strong, reliable first-timer pass |
| Excellent | 61-90° | High, bright, hard to miss |

Things worth knowing:
- A pass counts only while the Sun is at least 6° below your horizon. A pass that begins in brighter twilight is shown from the moment the sky is dark enough, so its rating can be lower than the full pass would suggest.
- A pass visible for less than one minute is left out.
- Brightness is an estimate at the pass's highest point. It agreed with published predictions to within 0.1 magnitude when checked, but flares off the solar arrays are not predicted.
- Weather never removes a pass from the list or the calendar. It adds a sky label, and alerts use it.

## Locations

- **Home** is the location set in Home Assistant, and follows it if you change it.
- **This device** is the person linked to the user who is logged in, using the location their Home Assistant app reports. If that person has no location, the browser's own location is used instead, rounded to about a kilometre. Browsers only share a location over HTTPS.
- Add **People** in the integration's options to give a person their own set of pass entities, for automations that follow someone who travels.

## Entities

All entities are on one **ISS Track** device.

| Entity | What it gives |
|---|---|
| `sensor.iss_track_latitude`, `sensor.iss_track_longitude` | Where the station is over the Earth |
| `sensor.iss_track_altitude`, `sensor.iss_track_speed` | Shown in your Home Assistant unit system |
| `sensor.iss_track_position` | The position as text, with `latitude` and `longitude` attributes. Add this one to a Map card to show the station |
| `sensor.iss_track_elevation`, `sensor.iss_track_azimuth`, `sensor.iss_track_distance` | Where the station is in your sky right now, and how far away over the ground |
| `binary_sensor.iss_track_pass_in_progress` | On for exactly as long as a matching pass is visible |
| `sensor.iss_track_next_pass` | Start time of the next matching pass. Attributes hold every detail: `end`, `peak_elevation`, `magnitude`, `quality`, `start_direction`, `end_direction`, `sky`, `alert` |
| `sensor.iss_track_next_pass_quality`, `sensor.iss_track_next_pass_peak_elevation`, `sensor.iss_track_next_pass_magnitude`, `sensor.iss_track_next_pass_sky` | The next pass's headline figures, for dashboards and conditions |
| `calendar.iss_track_passes` | Every matching pass for the next 10 days |
| `sensor.iss_track_tle_updated` | When the orbital data was last refreshed |

A tracked person gets the same observer entities with their name in the entity id, for example `sensor.iss_track_anna_next_pass`.

The pass sensor switches at the exact second a pass starts and ends. While a matching pass is in progress the live position entities update every 5 seconds.

## Dashboard card

The **ISS Track pass** card is in the card picker once the integration is set up. It shows the next matching pass with a countdown, and switches by itself to "Look NW, 34° above the horizon" while a pass is overhead.

```yaml
type: custom:iss-track-card
location: home      # home, device (each viewer sees their own), or person
person: person.anna # only when location is person
compact: false      # a single row for a crowded dashboard
upcoming: 2         # how many later passes to list, 0 to 3
```

## Automations

### Blueprint

[![Import the blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmattbratt%2Fiss_track%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fiss_track_pass_alert.yaml)

The **ISS Track - pass alert** blueprint runs your actions a few minutes before a matching pass, and optionally when it starts and ends. It can skip passes the sky forecast rules out. Your actions can use `{{ title }}`, `{{ message }}` and `{{ pass.peak_elevation }}` and the other pass details.

### By hand

Turn on a light for the length of every matching pass:

```yaml
automation:
  - alias: ISS overhead
    triggers:
      - trigger: state
        entity_id: binary_sensor.iss_track_pass_in_progress
        to: "on"
    conditions:
      - condition: template
        value_template: "{{ state_attr('binary_sensor.iss_track_pass_in_progress', 'alert') }}"
    actions:
      - action: light.turn_on
        target:
          entity_id: light.porch
```

Other triggers that work well:
- A **calendar** trigger on `calendar.iss_track_passes` with an offset, to act a fixed time before each pass.
- A **numeric state** trigger on `sensor.iss_track_elevation` above a value, to act whenever the station is high in your sky, visible or not.
- A **numeric state** trigger on `sensor.iss_track_distance` below a value, to act when the station is close over the ground.

## Development

The orbit, pass and brightness calculations live in `custom_components/iss_track/engine/` and do not import Home Assistant. Their tests check positions against satellite.js and passes against published predictions:

```
pip install sgp4 pytest
pytest tests
```

## Credits
- Map styling inspired by the European Space Agency's [ESA ISS Tracker](https://isstracker.spaceflight.esa.int/). Everything else is its own implementation.
- Uses [`sgp4`](https://github.com/brandon-rhodes/python-sgp4) for orbital calculations.
- Uses [`astronomy.browser.js`](https://github.com/cosinekitty/astronomy) for moon position calculations.
- Orbital elements courtesy of [Celestrak](https://celestrak.org/).

## License
MIT License
