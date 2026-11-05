/*
 * ISS Track sidebar panel: hosts the map page and hands it Home Assistant's
 * connection, so the page reads everything from the integration.
 */
class IssTrackPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._narrow = false;
    this._panel = null;
    this._frame = null;
    this._menu = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._menu) this._menu.hass = hass;
    this._push();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menu) this._menu.narrow = narrow;
    if (this._bar) this._bar.classList.toggle('narrow', Boolean(narrow));
  }

  set panel(panel) {
    this._panel = panel;
    this._build();
  }

  connectedCallback() {
    this._build();
  }

  _build() {
    if (this._frame || !this._panel || !this.isConnected) return;
    const config = this._panel.config || {};
    const base = config.static_url || '/iss_track_static';
    const query = new URLSearchParams({ v: config.version || '' });
    if (new URLSearchParams(window.location.search).has('settings')) query.set('settings', '1');

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:flex;flex-direction:column;height:100vh;height:100dvh;background:#444}
        .bar{display:none;align-items:center;height:var(--header-height,56px);
          padding:0 4px;box-sizing:border-box;font-size:20px;
          background:var(--app-header-background-color,#03a9f4);
          color:var(--app-header-text-color,#fff)}
        .bar.narrow{display:flex}
        .bar span{margin-left:8px}
        iframe{flex:1;min-height:0;width:100%;border:0;display:block}
      </style>
      <div class="bar"><ha-menu-button></ha-menu-button><span>ISS Track</span></div>
      <iframe title="ISS Track" allow="fullscreen; geolocation" allowfullscreen></iframe>`;
    this._bar = this.shadowRoot.querySelector('.bar');
    this._menu = this.shadowRoot.querySelector('ha-menu-button');
    this._menu.hass = this._hass;
    this._menu.narrow = this._narrow;
    this._bar.classList.toggle('narrow', Boolean(this._narrow));
    this._frame = this.shadowRoot.querySelector('iframe');
    this._frame.addEventListener('load', () => this._push());
    this._frame.src = `${base}/my_iss.html?${query.toString()}`;
  }

  _push() {
    const page = this._frame && this._frame.contentWindow;
    if (!page || !this._hass) return;
    try {
      if (typeof page.issTrackSetHass === 'function') page.issTrackSetHass(this._hass);
    } catch (err) {
      // The page is mid-navigation; the load event will push again.
    }
  }
}

if (!customElements.get('iss-track-panel')) {
  customElements.define('iss-track-panel', IssTrackPanel);
}
