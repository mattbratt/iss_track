/*
 * ISS Track shared frontend pieces: one pill, one sky dome, one set of labels
 * and formatters, used by both the map panel and the dashboard card.
 *
 * Nothing here computes the orbit. Every number is drawn from the
 * integration's WebSocket API.
 */

export const QUALITY_ORDER = ['excellent', 'good', 'fair', 'poor'];

export const QUALITY = {
  excellent: { label: 'Excellent', range: '61–90°', hint: 'High, bright, hard to miss' },
  good: { label: 'Good', range: '41–60°', hint: 'Strong, reliable first-timer pass' },
  fair: { label: 'Fair', range: '21–40°', hint: 'Visible if you know where to look' },
  poor: { label: 'Poor', range: '10–20°', hint: 'Easy to miss, often obstructed' },
};

export const SKY = {
  clear: 'Clear sky',
  partly_cloudy: 'Partly cloudy',
  cloudy: 'Cloudy',
  unknown: 'No forecast yet',
};

export const SKY_LIMITS = [
  ['any', 'Any'],
  ['partly_cloudy', 'Partly cloudy or better'],
  ['clear', 'Clear only'],
];

export const MAGNITUDE_BRIGHTEST = -4;
export const MAGNITUDE_FAINTEST = 1;
export const MAGNITUDE_STEP = 0.5;

const MAGNITUDE_HINTS = [
  [1, 'dark site only'],
  [0, 'fine away from city lights'],
  [-1, 'about as bright as Sirius'],
  [-2, 'easy from the suburbs'],
  [-3, 'unmissable, brighter than any star'],
  [-4, 'rivals Venus'],
];

const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

export function compass(azimuth) {
  return COMPASS[Math.floor((((azimuth % 360) + 360) % 360) / 22.5 + 0.5) % 16];
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]
  ));
}

export function formatMagnitude(magnitude) {
  const sign = magnitude < -0.05 ? '−' : magnitude > 0.05 ? '+' : '';
  return sign + Math.abs(magnitude).toFixed(1);
}

export function magnitudeHint(limit) {
  let hint = MAGNITUDE_HINTS[0][1];
  for (const [level, text] of MAGNITUDE_HINTS) {
    if (limit <= level) hint = text;
  }
  return hint;
}

export function formatCountdown(milliseconds) {
  const seconds = Math.round(milliseconds / 1000);
  if (seconds <= 0) return 'now';
  if (seconds < 60) return `in ${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `in ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `in ${hours} h ${minutes % 60} min`;
  return `in ${Math.floor(hours / 24)} d ${hours % 24} h`;
}

export function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} min ${seconds % 60} s` : `${seconds} s`;
}

function localeOf(hass) {
  const locale = (hass && hass.locale) || {};
  const options = {};
  if (hass && hass.config && hass.config.time_zone) options.timeZone = hass.config.time_zone;
  if (locale.time_format === '12') options.hour12 = true;
  if (locale.time_format === '24') options.hour12 = false;
  return { language: locale.language || undefined, options };
}

function dayNumber(date, timeZone) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(date).split('-').map(Number);
  return Date.UTC(parts[0], parts[1] - 1, parts[2]) / 86400000;
}

/* Day and time of a pass in Home Assistant's time zone: "Tonight", "6:42 PM". */
export function formatWhen(iso, hass, nowMs) {
  const { language, options } = localeOf(hass);
  const date = new Date(iso);
  const time = new Intl.DateTimeFormat(language, {
    ...options, hour: 'numeric', minute: '2-digit',
  }).format(date);
  const days = dayNumber(date, options.timeZone) - dayNumber(new Date(nowMs), options.timeZone);
  let day;
  if (days === 0) {
    const hour = Number(new Intl.DateTimeFormat('en-GB', {
      timeZone: options.timeZone, hour: '2-digit', hour12: false,
    }).format(date));
    day = hour >= 16 ? 'Tonight' : 'Today';
  } else if (days === 1) {
    day = 'Tomorrow';
  } else {
    day = new Intl.DateTimeFormat(language, {
      timeZone: options.timeZone, weekday: 'short', month: 'short', day: 'numeric',
    }).format(date);
  }
  return { day, time };
}

/* The first pass still to come (or in progress) that matches the settings. */
export function nextMatching(passes, nowMs) {
  return passes.find((p) => p.matches && Date.parse(p.end) >= nowMs) || null;
}

export function isLive(pass, nowMs) {
  return Date.parse(pass.start) <= nowMs && nowMs <= Date.parse(pass.end);
}

/* The best pass that does not match, for the "nothing matches" state. */
export function bestOther(passes, nowMs) {
  let best = null;
  for (const p of passes) {
    if (p.matches || Date.parse(p.end) < nowMs) continue;
    if (!best || p.peak_elevation > best.peak_elevation) best = p;
  }
  return best;
}

/* Where to look right now, read off the pass's own path. */
export function liveLook(pass, nowMs) {
  const path = pass.path || [];
  if (!path.length) return null;
  const elapsed = (nowMs - Date.parse(pass.start)) / 1000;
  const duration = Math.max(1, pass.duration_seconds);
  const t = Math.min(Math.max(elapsed, 0), duration);
  let i = 0;
  while (i < path.length - 2 && path[i + 1][0] <= t) i += 1;
  const a = path[i];
  const b = path[Math.min(i + 1, path.length - 1)];
  const span = Math.max(1e-6, b[0] - a[0]);
  const f = Math.min(Math.max((t - a[0]) / span, 0), 1);
  const turn = ((b[1] - a[1] + 540) % 360) - 180;
  const azimuth = (a[1] + turn * f + 360) % 360;
  const elevation = a[2] + (b[2] - a[2]) * f;
  return {
    azimuth,
    elevation,
    direction: compass(azimuth),
    secondsLeft: Math.max(0, duration - elapsed),
    progress: t / duration,
  };
}

export function pill(kind, text, title = '') {
  const tip = title ? ` title="${escapeHtml(title)}"` : '';
  return `<span class="iss-pill ${kind}"${tip}>${escapeHtml(text)}</span>`;
}

export function qualityPill(pass, withDegrees = true) {
  const quality = QUALITY[pass.quality];
  const peak = Math.round(pass.peak_elevation);
  return pill(
    pass.quality,
    withDegrees ? `${quality.label}, ${peak}°` : quality.label,
    `PASS QUALITY: highest point ${peak}° above the horizon. ${quality.label} is ${quality.range}. ${quality.hint}.`,
  );
}

export function magnitudePill(pass, short = false) {
  return pill(
    'good',
    `${short ? 'Mag' : 'Magnitude'} ${formatMagnitude(pass.magnitude)}`,
    'BRIGHTNESS: estimated magnitude at the highest point. Lower is brighter; '
      + 'Venus is about −4, the brightest star −1.5.',
  );
}

export function skyPill(pass) {
  if (pass.sky === 'unknown') return '';
  return pill(
    pass.sky === 'cloudy' ? 'dim' : 'neutral',
    SKY[pass.sky],
    'SKY FORECAST: from your weather entity, for the time of this pass.',
  );
}

/* One sentence on how the pass begins and ends. */
export function describePass(pass) {
  const start = pass.starts_in_shadow
    ? `Appears out of Earth's shadow in the ${pass.start_direction}`
    : `Rises in the ${pass.start_direction}`;
  const end = pass.ends_in_shadow
    ? `fades into Earth's shadow in the ${pass.end_direction}`
    : `sets in the ${pass.end_direction}`;
  return `${start}, ${end}`;
}

/*
 * The sky dome: horizon, the pass's arc from its own path, direction labels,
 * and either the peak marker or the live position.
 */
export function domeSvg(pass, progress = null) {
  const left = 16;
  const right = 174;
  const horizon = 92;
  const top = 12;
  const duration = Math.max(1, pass.duration_seconds);
  const at = (seconds, elevation) => [
    left + (right - left) * (seconds / duration),
    horizon - (horizon - top) * (Math.max(0, elevation) / 90),
  ];
  const path = (pass.path && pass.path.length) ? pass.path
    : [[0, 0, pass.start_elevation], [duration, 0, pass.end_elevation]];
  const points = path.map(([s, , el]) => at(s, el).map((v) => v.toFixed(1)).join(',')).join(' ');
  let peak = path[0];
  for (const point of path) if (point[2] > peak[2]) peak = point;
  const [px, py] = at(peak[0], peak[2]);
  let marker;
  if (progress === null) {
    const anchor = px > 130 ? 'end' : 'start';
    const tx = px > 130 ? px - 8 : px + 8;
    marker = `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4" class="iss-dome-arc-fill"/>`
      + `<text x="${tx.toFixed(1)}" y="${Math.max(11, py - 6).toFixed(1)}" text-anchor="${anchor}" class="iss-dome-text">${Math.round(pass.peak_elevation)}°</text>`;
  } else {
    const look = liveLookAt(path, duration, progress);
    const [lx, ly] = at(look[0], look[1]);
    marker = `<circle cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="7" class="iss-dome-arc-fill"/>`;
  }
  const description = `Pass from ${pass.start_direction} to ${pass.end_direction}, `
    + `highest at ${Math.round(pass.peak_elevation)} degrees`;
  return `<svg class="iss-dome" viewBox="0 0 190 112" role="img" aria-label="${escapeHtml(description)}">`
    + `<path d="M${left} ${horizon} A${(right - left) / 2} ${horizon - top} 0 0 1 ${right} ${horizon}" class="iss-dome-sky"/>`
    + `<line x1="6" y1="${horizon}" x2="184" y2="${horizon}" class="iss-dome-horizon"/>`
    + `<polyline points="${points}" class="${progress === null ? 'iss-dome-arc' : 'iss-dome-arc dim'}"/>`
    + marker
    + `<text x="${left - 8}" y="108" class="iss-dome-label">${escapeHtml(pass.start_direction)}</text>`
    + `<text x="${right + 8}" y="108" text-anchor="end" class="iss-dome-label">${escapeHtml(pass.end_direction)}</text>`
    + '</svg>';
}

function liveLookAt(path, duration, progress) {
  const t = Math.min(Math.max(progress, 0), 1) * duration;
  let i = 0;
  while (i < path.length - 2 && path[i + 1][0] <= t) i += 1;
  const a = path[i];
  const b = path[Math.min(i + 1, path.length - 1)];
  const f = Math.min(Math.max((t - a[0]) / Math.max(1e-6, b[0] - a[0]), 0), 1);
  return [t, a[2] + (b[2] - a[2]) * f];
}

/* Why "This device" has no location, in words. */
export function unavailableText(observer) {
  const reason = observer.reason || '';
  if (reason.includes('no_person')) {
    return "Your Home Assistant user isn't linked to a person. Link one under Settings, People, "
      + 'or open Home Assistant over HTTPS so this browser can share its location.';
  }
  if (reason.includes('denied')) {
    return "This device hasn't reported a location, and the browser's location request was declined.";
  }
  if (reason.includes('insecure')) {
    return "This device hasn't reported a location to Home Assistant yet. Turn on location in the "
      + 'Home Assistant app, or open Home Assistant over HTTPS so this browser can share it.';
  }
  return "This device hasn't reported a location to Home Assistant yet.";
}

function browserPosition() {
  return new Promise((resolve, reject) => {
    if (!window.isSecureContext || !navigator.geolocation) {
      reject(new Error('insecure'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position.coords),
      () => reject(new Error('denied')),
      { timeout: 10000, maximumAge: 600000 },
    );
  });
}

/*
 * Passes for an observer: "home", a person's entity id, or "device".
 * "device" is the person linked to the logged-in user; if that person has no
 * location, the browser's own location is used, rounded to about a kilometre.
 */
export async function fetchPasses(hass, choice) {
  if (choice !== 'device') {
    return hass.callWS({ type: 'iss_track/passes', observer: choice || 'home' });
  }
  const result = await hass.callWS({ type: 'iss_track/passes', observer: 'me' });
  if (result.observer.available) return result;
  try {
    const coords = await browserPosition();
    return await hass.callWS({
      type: 'iss_track/passes',
      latitude: Number(coords.latitude.toFixed(2)),
      longitude: Number(coords.longitude.toFixed(2)),
    });
  } catch (err) {
    result.observer.reason = `${result.observer.reason}+${err.message}`;
    return result;
  }
}

/*
 * Styles for the pill and the dome. Each host (panel or card) supplies the
 * colours through the --iss-* custom properties.
 */
export const SHARED_CSS = `
.iss-pill{display:inline-flex;align-items:center;font-size:12px;line-height:1;padding:4px 10px;
  border-radius:999px;white-space:nowrap;font-weight:500;
  background:var(--iss-neutral-bg);color:var(--iss-text2)}
.iss-pill.excellent,.iss-pill.live,.iss-pill.on{background:var(--iss-ok-bg);color:var(--iss-ok)}
.iss-pill.good{background:var(--iss-info-bg);color:var(--iss-info)}
.iss-pill.fair{background:var(--iss-warn-bg);color:var(--iss-warn)}
.iss-pill.dim{color:var(--iss-text3)}
.iss-dome{display:block;width:100%;height:auto}
.iss-dome-sky{fill:none;stroke:var(--iss-border);stroke-width:1}
.iss-dome-horizon{stroke:var(--iss-text3);stroke-width:1.5}
.iss-dome-arc{fill:none;stroke:var(--iss-ok);stroke-width:4;stroke-linecap:round;stroke-linejoin:round}
.iss-dome-arc.dim{stroke:var(--iss-text3);stroke-width:3}
.iss-dome-arc-fill{fill:var(--iss-ok)}
.iss-dome-label{fill:var(--iss-text3);font-size:14px}
.iss-dome-text{fill:var(--iss-text2);font-size:14px}
`;
