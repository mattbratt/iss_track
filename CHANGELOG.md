# Changelog

All notable changes to ISS Track are listed here, newest first.

## 2.0.1 - 2026-11-04

### Added
- **A note when the station passes overhead unseen.** The station often crosses your sky with nothing to see: at night it is in Earth's shadow, and by day your sky is too bright. When that is about to happen, or is happening, the panel now says so above the next pass, with the time, how high it gets and the reason. On the map, that stretch of track is drawn dashed and grey instead of green.
- The note appears only while the station is above your horizon or will be within 30 minutes. An unseen overflight is not a pass, so the entities, the calendar and alerts are unchanged.

## 2.0.0 - 2026-11-04

ISS Track now tells you when you can see the station, not only where it is. Everything it shows is worked out once, inside Home Assistant, and is available to automations.

### Added
- **Visible pass predictions.** Every pass you can see in the next 10 days: the station in sunlight, your sky dark, and the station at least 10° above the horizon.
- **Pass quality and brightness.** Each pass is rated Poor, Fair, Good or Excellent by how high it gets, with an estimated magnitude.
- **Pass settings.** Choose which qualities count, a minimum brightness, and evening passes, morning passes or both. One set of settings is shared by the panel, the card, the calendar and the entities. Change it from the gear in the panel or from the integration's Configure dialog.
- **Entities.** The station's latitude, longitude, altitude, speed and position; its elevation, azimuth and ground distance from you; a pass-in-progress sensor; and the next pass's time, quality, peak elevation, magnitude and sky. This answers the request in issue #2.
- **Calendar.** `calendar.iss_track_passes` holds every matching pass, so a calendar trigger can act ahead of one.
- **Dashboard card.** "ISS Track pass" shows a countdown to the next pass and switches to "Look NW, 34° above the horizon" while one is overhead. It has a compact row layout.
- **Visible passes in the panel.** A list under the map, a ring on the map showing where the station must be for you to see it, and the next matching pass drawn on the map.
- **This device.** Passes for where you are now, using the person linked to your Home Assistant user, or the browser's location when that is not available.
- **People.** Optionally give chosen people their own pass entities, following the location their Home Assistant app reports.
- **Sky forecast.** Pick a weather entity and each pass shows the forecast sky. Alerts can skip a pass that is too cloudy. A pass with no forecast yet is never skipped.
- **Blueprint.** "ISS Track - pass alert" runs your actions before a matching pass and when it starts and ends.
- **Out-of-date warning.** A repair notice appears if the orbital data has not refreshed for more than three days.
- **Download count.** Releases now carry an `iss_track.zip` asset, which lets the Marketplace show how many times ISS Track has been downloaded.

### Changed
- **The orbit is calculated by the integration, not the browser.** The map panel draws what the integration sends it, so the panel, the card and the entities always agree. The panel no longer contacts Celestrak itself.
- **Orbital data survives an outage.** The last good data is kept on disk and used until Celestrak can be reached again. The panel's built-in fallback data, which went stale, is gone.
- **Orbit paths on the map are always current.** They were refreshed every 30 minutes before; they now follow the station continuously.
- **Installation is through the Marketplace** (Settings > Marketplace) on Home Assistant 2026.11 and newer, and through HACS on older versions.

### Upgrade notes
- **Home Assistant 2024.12 or newer is required.**
- **Restart Home Assistant after updating.** A new Python package (`sgp4`) is installed during the restart.
- **Your existing setup carries over.** The unit preference is kept, and the new pass settings start at their defaults: Good and Excellent passes, magnitude -2 or brighter, evenings only.
- **The map page no longer works when opened by its own address.** Open ISS Track from the sidebar. If you embedded `/iss_track_static/my_iss.html` in a dashboard, use the new dashboard card instead.
- **New entities are recorded.** The live position entities update every 30 seconds by default. Raise the update interval in the Configure dialog, or exclude them from the recorder, if you want a smaller database.

## 1.1.4 - 2026-08-03
- Fixed the tooltip's position and overflow at the screen edge.
- Fixed the live video window being hidden in fullscreen.

## 1.1.3 - 2026-08-03
- Added a default unit preference (imperial or metric).
- Fixed the status bar in fullscreen.
- Updated the tooltip.

## 1.1.2 - 2026-08-03
- Fixed the integration manifest.
- Updated the live video link.

## 1.1.1 - 2026-07-28
- Added brand images.
- Added validation workflows.

## 1.1.0 - 2026-07-28
- Packaged for HACS.
