/*
 * ISS Track dashboard card: the next visible pass, and where to look while
 * one is overhead. Draws only what the integration's API returns.
 */
const VERSION = new URL(import.meta.url).searchParams.get('v') || '';
const S = await import(`./iss-track-shared.js?v=${VERSION}`);

const REFRESH_MS = 10 * 60 * 1000;
const PANEL_PATH = '/iss-track';

const CARD_CSS = `
:host{
  --iss-text:var(--primary-text-color);
  --iss-text2:var(--secondary-text-color);
  --iss-text3:var(--disabled-text-color, var(--secondary-text-color));
  --iss-border:var(--divider-color);
  --iss-ok:var(--success-color,#43a047);
  --iss-info:var(--info-color,#039be5);
  --iss-warn:var(--warning-color,#ffa600);
  --iss-ok-bg:color-mix(in srgb,var(--iss-ok) 18%,transparent);
  --iss-info-bg:color-mix(in srgb,var(--iss-info) 18%,transparent);
  --iss-warn-bg:color-mix(in srgb,var(--iss-warn) 20%,transparent);
  --iss-neutral-bg:color-mix(in srgb,var(--iss-text2) 14%,transparent);
  display:block;
}
ha-card{padding:14px 16px;color:var(--iss-text);box-sizing:border-box}
ha-card.live{border-color:var(--iss-ok);box-shadow:inset 0 0 0 1px var(--iss-ok)}
.head{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--iss-text2);margin-bottom:10px}
.head ha-icon{--mdc-icon-size:18px}
.head .iss-pill{margin-left:auto}
.head .iss-pill ha-icon{--mdc-icon-size:13px;margin-right:4px}
.hero{display:grid;grid-template-columns:minmax(0,1fr) 128px;gap:8px;align-items:center}
.big{font-size:22px;font-weight:500;line-height:1.25;margin:0 0 4px}
.sub{font-size:13px;color:var(--iss-text2);margin:0 0 10px}
.pills{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.row{display:flex;align-items:center;gap:8px;font-size:13px;padding:7px 0;border-top:1px solid var(--iss-border)}
.row .when{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row .mag{color:var(--iss-text2);width:36px;text-align:right}
.bar{height:4px;background:var(--iss-neutral-bg);border-radius:999px;margin:2px 0 8px;overflow:hidden}
.bar div{height:4px;background:var(--iss-ok);border-radius:999px}
.left{font-size:13px;margin:0 0 4px}
.left span{color:var(--iss-text2)}
.note{font-size:13px;color:var(--iss-text2);margin:0 0 10px}
.title{font-size:15px;font-weight:500;margin:0 0 4px}
button{font:inherit;font-size:13px;color:var(--primary-color);background:none;cursor:pointer;
  border:1px solid var(--iss-border);border-radius:8px;padding:6px 12px}
button:hover{background:var(--iss-neutral-bg)}
.compact{display:flex;align-items:center;gap:10px}
.compact ha-icon{color:var(--iss-text2);--mdc-icon-size:22px}
.compact .text{flex:1;min-width:0}
.compact .title{font-size:14px;margin:0}
.compact .sub{margin:0;font-size:12px}
`;

const LOCATION_ICON = { home: 'mdi:home', device: 'mdi:crosshairs-gps', person: 'mdi:account' };

class IssTrackCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;
    this._data = null;
    this._error = null;
    this._loading = false;
    this._loadedAt = 0;
    this._watched = null;
    this._signature = '';
    this._timer = null;
  }

  static getStubConfig() {
    return { location: 'home', upcoming: 2 };
  }

  static getConfigForm() {
    const labels = {
      location: 'Location',
      person: 'Person (when Location is "A person")',
      compact: 'Compact row',
      upcoming: 'Upcoming passes to list',
    };
    return {
      schema: [
        {
          name: 'location',
          selector: {
            select: {
              mode: 'dropdown',
              options: [
                { value: 'home', label: 'Home' },
                { value: 'device', label: 'This device (each viewer sees their own)' },
                { value: 'person', label: 'A person' },
              ],
            },
          },
        },
        { name: 'person', selector: { entity: { domain: 'person' } } },
        { name: 'compact', selector: { boolean: {} } },
        { name: 'upcoming', selector: { number: { min: 0, max: 3, mode: 'box' } } },
      ],
      computeLabel: (schema) => labels[schema.name],
    };
  }

  setConfig(config) {
    const location = config.location || 'home';
    if (!['home', 'device', 'person'].includes(location)) {
      throw new Error('location must be home, device or person');
    }
    if (location === 'person' && !config.person) {
      throw new Error('Choose a person, or set Location to Home or This device');
    }
    const upcoming = Number(config.upcoming === undefined ? 2 : config.upcoming);
    this._config = {
      location,
      person: config.person,
      compact: Boolean(config.compact),
      upcoming: Math.min(3, Math.max(0, Number.isFinite(upcoming) ? upcoming : 2)),
    };
    this._data = null;
    this._loadedAt = 0;
    this._signature = '';
    if (this._hass) this._load();
  }

  set hass(hass) {
    this._hass = hass;
    // The next-pass sensor changes whenever passes or settings change.
    const watched = hass.states['sensor.iss_track_next_pass'] || null;
    const stale = Date.now() - this._loadedAt > REFRESH_MS;
    if (this._config && (watched !== this._watched || stale)) {
      this._watched = watched;
      this._load();
    }
  }

  getCardSize() {
    return this._config && this._config.compact ? 1 : 4;
  }

  connectedCallback() {
    this._timer = window.setInterval(() => this._tick(), 1000);
    this._render();
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
    this._timer = null;
  }

  _choice() {
    const { location, person } = this._config;
    return location === 'person' ? person : location;
  }

  async _load() {
    if (this._loading || !this._hass || !this._config) return;
    this._loading = true;
    this._loadedAt = Date.now();
    try {
      this._data = await S.fetchPasses(this._hass, this._choice());
      this._error = null;
    } catch (err) {
      this._error = (err && err.message) || 'ISS Track is not ready';
      // Try again soon rather than waiting out the full refresh period.
      this._loadedAt = Date.now() - REFRESH_MS + 30000;
    }
    this._loading = false;
    this._signature = '';
    this._render();
  }

  _state(now) {
    if (this._error && !this._data) return { kind: 'error' };
    if (!this._data) return { kind: 'loading' };
    if (!this._data.observer.available) return { kind: 'unavailable' };
    const next = S.nextMatching(this._data.passes, now);
    if (!next) return { kind: 'none' };
    return { kind: S.isLive(next, now) ? 'live' : 'next', pass: next };
  }

  _tick() {
    if (!this._config || !this.isConnected) return;
    const now = Date.now();
    const state = this._state(now);
    const signature = `${state.kind}|${state.pass ? state.pass.start : ''}`;
    if (signature !== this._signature) {
      this._render();
      return;
    }
    const root = this.shadowRoot;
    if (state.kind === 'next') {
      const big = root.getElementById('big');
      if (big) big.textContent = this._countdown(state.pass, now);
    } else if (state.kind === 'live') {
      this._updateLive(state.pass, now);
    }
  }

  _countdown(pass, now) {
    const text = S.formatCountdown(Date.parse(pass.start) - now);
    return this._config.compact ? `Pass ${text}` : text;
  }

  _updateLive(pass, now) {
    const root = this.shadowRoot;
    const look = S.liveLook(pass, now);
    if (!look) return;
    const big = root.getElementById('big');
    const sub = root.getElementById('sub');
    const bar = root.getElementById('bar');
    const left = root.getElementById('left');
    const dome = root.getElementById('dome');
    const up = `${Math.round(look.elevation)}° above the horizon`;
    if (this._config.compact) {
      if (big) big.textContent = `Look ${look.direction}, ${Math.round(look.elevation)}° up`;
      if (sub) sub.textContent = `${S.formatDuration(look.secondsLeft)} left`;
      return;
    }
    if (big) big.textContent = `Look ${look.direction}`;
    if (sub) sub.textContent = up;
    if (bar) bar.style.width = `${Math.round(look.progress * 100)}%`;
    if (left) left.textContent = `${S.formatDuration(look.secondsLeft)} left`;
    if (dome) dome.innerHTML = S.domeSvg(pass, look.progress);
  }

  _header(extra) {
    const observer = this._data ? this._data.observer : null;
    const icon = LOCATION_ICON[this._config.location];
    const chip = observer && !extra
      ? `<span class="iss-pill" title="LOCATION: passes are predicted for ${S.escapeHtml(observer.name)}."><ha-icon icon="${icon}"></ha-icon>${S.escapeHtml(observer.name)}</span>`
      : (extra || '');
    return `<div class="head"><ha-icon icon="mdi:space-station"></ha-icon>ISS Track${chip}</div>`;
  }

  _upcomingRows(after, now) {
    if (!this._config.upcoming) return '';
    const rows = this._data.passes
      .filter((p) => p.matches && Date.parse(p.start) > Date.parse(after.start))
      .slice(0, this._config.upcoming);
    return rows.map((p) => {
      const when = S.formatWhen(p.start, this._hass, now);
      return `<div class="row"><span class="when">${S.escapeHtml(`${when.day}, ${when.time}`)}</span>`
        + `${S.qualityPill(p)}<span class="mag" title="BRIGHTNESS: estimated magnitude. Lower is brighter.">${S.formatMagnitude(p.magnitude)}</span></div>`;
    }).join('');
  }

  _render() {
    if (!this._config) return;
    const now = Date.now();
    const state = this._state(now);
    this._signature = `${state.kind}|${state.pass ? state.pass.start : ''}`;
    const compact = this._config.compact;
    let body;
    let live = false;

    if (state.kind === 'loading') {
      body = `${this._header()}<p class="note">Loading passes…</p>`;
    } else if (state.kind === 'error') {
      body = `${this._header()}<p class="title">ISS Track isn't ready</p><p class="note">${S.escapeHtml(this._error)}</p>`;
    } else if (state.kind === 'unavailable') {
      body = `${this._header()}<p class="title">No location for this device</p>`
        + `<p class="note">${S.escapeHtml(S.unavailableText(this._data.observer))}</p>`;
    } else if (state.kind === 'none') {
      const other = S.bestOther(this._data.passes, now);
      let hint = 'No visible passes at all in that time.';
      if (other) {
        const when = S.formatWhen(other.start, this._hass, now);
        hint = `The best one coming is ${S.QUALITY[other.quality].label}, ${Math.round(other.peak_elevation)}°, ${when.day} at ${when.time}.`;
      }
      body = compact
        ? `<div class="compact"><ha-icon icon="mdi:space-station"></ha-icon><div class="text"><p class="title">No matching passes for 10 days</p><p class="sub">${S.escapeHtml(hint)}</p></div></div>`
        : `${this._header()}<p class="title">No matching passes for 10 days</p><p class="note">${S.escapeHtml(hint)}</p>`
          + '<button id="settings" title="PASS SETTINGS: open the ISS Track panel to change which passes count.">Adjust pass settings</button>';
    } else if (state.kind === 'live') {
      live = true;
      const pass = state.pass;
      body = compact
        ? `<div class="compact"><ha-icon icon="mdi:space-station"></ha-icon><div class="text"><p class="title" id="big"></p><p class="sub" id="sub"></p></div>${S.pill('live', 'Visible now', 'VISIBLE NOW: a pass that matches your settings is overhead.')}</div>`
        : `${this._header(S.pill('live', 'Visible now', 'VISIBLE NOW: a pass that matches your settings is overhead.'))}`
          + '<div class="hero"><div><p class="big" id="big"></p><p class="sub" id="sub"></p></div><div id="dome"></div></div>'
          + '<div class="bar"><div id="bar" style="width:0%"></div></div>'
          + `<p class="left"><b id="left"></b> <span>· peaks at ${Math.round(pass.peak_elevation)}°, ${S.escapeHtml(S.describePass(pass).split(', ')[1])}</span></p>`;
    } else {
      const pass = state.pass;
      const when = S.formatWhen(pass.start, this._hass, now);
      const sub = `${when.day} at ${when.time}, ${S.formatDuration(pass.duration_seconds)}`;
      body = compact
        ? `<div class="compact"><ha-icon icon="mdi:space-station"></ha-icon><div class="text"><p class="title" id="big">${S.escapeHtml(this._countdown(pass, now))}</p>`
          + `<p class="sub">${S.escapeHtml(`${when.day} ${when.time}, ${pass.start_direction} to ${pass.end_direction}`)}</p></div>${S.qualityPill(pass, false)}</div>`
        : `${this._header()}<div class="hero"><div><p class="big" id="big">${S.escapeHtml(this._countdown(pass, now))}</p>`
          + `<p class="sub" title="${S.escapeHtml(S.describePass(pass))}">${S.escapeHtml(sub)}</p></div><div>${S.domeSvg(pass)}</div></div>`
          + `<div class="pills">${S.qualityPill(pass)}${S.magnitudePill(pass, true)}${S.skyPill(pass)}</div>`
          + this._upcomingRows(pass, now);
    }

    this.shadowRoot.innerHTML = `<style>${S.SHARED_CSS}${CARD_CSS}</style><ha-card class="${live ? 'live' : ''}">${body}</ha-card>`;
    if (live) this._updateLive(state.pass, now);
    const button = this.shadowRoot.getElementById('settings');
    if (button) {
      button.addEventListener('click', () => {
        window.history.pushState(null, '', `${PANEL_PATH}?settings=1`);
        window.dispatchEvent(new CustomEvent('location-changed', { bubbles: true, composed: true }));
      });
    }
  }
}

if (!customElements.get('iss-track-card')) {
  customElements.define('iss-track-card', IssTrackCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === 'iss-track-card')) {
  window.customCards.push({
    type: 'iss-track-card',
    name: 'ISS Track pass',
    description: 'The next visible ISS pass, and where to look while one is overhead.',
    preview: true,
    documentationURL: 'https://github.com/mattbratt/iss_track',
  });
}
