
const state = {
  stops: [],

  markers: [],

  routeLayers: [],

  currentMode: 'trip',
  vehicles: [
    { capacity: 10, label: 'Vehicle 1' },
    { capacity: 10, label: 'Vehicle 2' },
  ],
};

const VEHICLE_COLORS = ['#5b7fff', '#ff6b6b', '#ffd93d', '#6bcb77', '#c77dff'];


const map = L.map('map', { zoomControl: true }).setView([20.5937, 78.9629], 5);
map.zoomControl.setPosition('topright');

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 19,
}).addTo(map);

map.on('click', e => addStop(e.latlng.lat, e.latlng.lng));


function addStop(lat, lng, label) {
  if (state.stops.length >= 20) {
    alert('Maximum 20 stops');
    return;
  }
  const idx = state.stops.length;
  const name = label || `${lat.toFixed(4)}, ${lng.toFixed(4)}`;


  if (!label) {
    fetch('/reverse-geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lng }),
    })
      .then(r => r.json())
      .then(data => {
        const short = shortenAddress(data.display_name);
        state.stops[idx].label = short;
        renderStopList();
        updateSelectBoxes();
      })
      .catch(() => {});
  }

  state.stops.push({ lat, lng, label: name });

  const marker = L.marker([lat, lng], { icon: makeIcon(idx) })
    .addTo(map)
    .bindPopup(`<b>Stop ${idx + 1}</b><br>${name}`);

  marker.on('dragend', e => {
    const pos = e.target.getLatLng();
    state.stops[idx].lat = pos.lat;
    state.stops[idx].lng = pos.lng;
    state.stops[idx].label = `${pos.lat.toFixed(4)}, ${pos.lng.toFixed(4)}`;
    renderStopList();
    clearRoutes();
    fetch('/reverse-geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat: pos.lat, lng: pos.lng }),
    })
      .then(r => r.json())
      .then(data => {
        state.stops[idx].label = shortenAddress(data.display_name);
        renderStopList();
      })
      .catch(() => {});
  });

  state.markers.push(marker);
  renderStopList();
  updateSelectBoxes();
  clearRoutes();
  document.getElementById('mapHint').style.opacity = '0';
}

function removeStop(idx) {
  state.stops.splice(idx, 1);
  if (state.markers[idx]) {
    state.markers[idx].remove();
    state.markers.splice(idx, 1);
  }

  state.markers.forEach((m, i) => m.setIcon(makeIcon(i)));
  renderStopList();
  updateSelectBoxes();
  clearRoutes();
}

function clearAllStops() {
  state.stops = [];
  state.markers.forEach(m => m.remove());
  state.markers = [];
  clearRoutes();
  renderStopList();
  updateSelectBoxes();
  document.getElementById('mapHint').style.opacity = '1';
  document.getElementById('resultsPanel').classList.add('hidden');
  document.getElementById('fallbackWarning').classList.add('hidden');
}


function clearRoutes() {
  state.routeLayers.forEach(l => l.remove());
  state.routeLayers = [];
  document.getElementById('resultsPanel').classList.add('hidden');
  document.getElementById('fallbackWarning').classList.add('hidden');
}

function drawPolyline(coords, color = '#5b7fff', weight = 4) {
  const layer = L.polyline(coords, {
    color,
    weight,
    opacity: 0.85,
    lineJoin: 'round',
    lineCap: 'round',
  }).addTo(map);
  state.routeLayers.push(layer);
  return layer;
}


function makeIcon(idx, color = '#5b7fff') {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
      <path d="M14 0C6.268 0 0 6.268 0 14c0 9.333 14 22 14 22S28 23.333 28 14C28 6.268 21.732 0 14 0z"
            fill="${color}" stroke="rgba(0,0,0,0.3)" stroke-width="1"/>
      <text x="14" y="19" text-anchor="middle" fill="white" font-size="12" font-weight="bold"
            font-family="Inter, system-ui, sans-serif">${idx + 1}</text>
    </svg>`;
  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [28, 36],
    iconAnchor: [14, 36],
    popupAnchor: [0, -36],
  });
}


async function addStopFromInput() {
  const input = document.getElementById('stopInput');
  const query = input.value.trim();
  if (!query) return;
  try {
    const resp = await fetch('/geocode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (!resp.ok) throw new Error('Not found');
    const data = await resp.json();
    addStop(data.lat, data.lng, shortenAddress(data.display_name));
    map.setView([data.lat, data.lng], 13);
    input.value = '';
  } catch {
    alert('Location not found. Try a more specific address.');
  }
}

document.getElementById('stopInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') addStopFromInput();
});

/* ── Render helpers ────────────────────────────────────────────────────── */
function renderStopList() {
  const ul = document.getElementById('stopList');
  ul.innerHTML = '';
  state.stops.forEach((s, i) => {
    const li = document.createElement('li');
    li.className = 'stop-item';
    li.innerHTML = `
      <div class="stop-badge">${i + 1}</div>
      <span class="stop-name" title="${s.label}">${s.label}</span>
      <button class="stop-remove" onclick="removeStop(${i})" title="Remove">×</button>`;
    ul.appendChild(li);
  });
}

function updateSelectBoxes() {
  const opts = state.stops.map((s, i) => `<option value="${i}">${i + 1}. ${s.label.slice(0, 25)}</option>`).join('');
  ['startSelect', 'endSelect', 'depotSelect'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = opts;
  });
  if (document.getElementById('endSelect')) {
    document.getElementById('endSelect').value = String(Math.max(0, state.stops.length - 1));
  }
}

function shortenAddress(addr) {
  const parts = addr.split(',');
  return parts.slice(0, 2).join(',').trim();
}

function formatDuration(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}


function buildGoogleMapsUrl(orderedIndices) {
  const coords = orderedIndices.map(i => state.stops[i]);

  if (coords.length < 2) return null;

  const origin      = `${coords[0].lat},${coords[0].lng}`;
  const destination = `${coords[coords.length - 1].lat},${coords[coords.length - 1].lng}`;
  const middle      = coords.slice(1, -1);

  const params = new URLSearchParams({
    api: '1',
    origin,
    destination,
    travelmode: 'driving',
  });

  if (middle.length > 0) {

    const waypoints = middle.slice(0, 8).map(s => `${s.lat},${s.lng}`).join('|');
    params.set('waypoints', waypoints);
  }

  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function googleMapsButtonHTML(orderedIndices, label = 'Open in Google Maps') {
  const url = buildGoogleMapsUrl(orderedIndices);
  if (!url) return '';

  const truncated = orderedIndices.length > 10;
  const warning   = truncated
    ? ' title="Google Maps supports up to 10 stops — first 10 shown"'
    : '';
  const suffix    = truncated ? ' (first 10)' : '';

  return `
    <a href="${url}" target="_blank" rel="noopener" class="btn-gmaps"${warning}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"
              fill="#fff" opacity="0.9"/>
        <circle cx="12" cy="9" r="2.5" fill="#1a73e8"/>
      </svg>
      ${label}${suffix}
    </a>`;
}

function switchMode(mode) {
  state.currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  document.getElementById('tripOptions').classList.toggle('hidden', mode !== 'trip');
  document.getElementById('fleetOptions').classList.toggle('hidden', mode !== 'fleet');
  const btn = document.getElementById('optimizeBtnText');
  btn.textContent = mode === 'trip' ? 'Optimize Route' : 'Optimize Fleet';
  
  const slider = document.getElementById('modeSlider');
  if (slider) {
    slider.style.transform = mode === 'fleet' ? 'translateX(100%)' : 'translateX(0)';
  }
  
  clearRoutes();
}

function runOptimize() {
  if (state.currentMode === 'trip') optimizeTrip();
  else optimizeFleet();
}

/* ── Loading state ──────────────────────────────────────────────────────── */
function setLoading(on) {
  const btn = document.getElementById('optimizeBtn');
  btn.disabled = on;
  document.getElementById('optimizeBtnText').classList.toggle('hidden', on);
  document.getElementById('optimizeSpinner').classList.toggle('hidden', !on);
}
