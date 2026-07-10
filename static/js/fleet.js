/* ── Fleet Optimizer (VRP) ──────────────────────────────────────────────── */

renderVehicleList();


function addVehicle() {
  if (state.vehicles.length >= 5) {
    alert('Maximum 5 vehicles');
    return;
  }
  const idx = state.vehicles.length + 1;
  state.vehicles.push({ capacity: 10, label: `Vehicle ${idx}` });
  renderVehicleList();
}

function removeVehicle(idx) {
  if (state.vehicles.length <= 1) return;
  state.vehicles.splice(idx, 1);
  renderVehicleList();
}

function renderVehicleList() {
  const ul = document.getElementById('vehicleList');
  if (!ul) return;
  ul.innerHTML = '';
  state.vehicles.forEach((v, i) => {
    const li = document.createElement('li');
    li.className = 'vehicle-item';
    li.innerHTML = `
      <div class="vehicle-color-dot" style="background:${VEHICLE_COLORS[i]}"></div>
      <span class="vehicle-label">${v.label}</span>
      <span style="font-size:11px;color:var(--text-muted)">Cap:</span>
      <input class="vehicle-cap-input" type="number" min="1" max="50"
             value="${v.capacity}"
             onchange="state.vehicles[${i}].capacity = parseInt(this.value) || 1"
             title="Capacity" />
      <button class="vehicle-remove" onclick="removeVehicle(${i})" title="Remove">×</button>`;
    ul.appendChild(li);
  });
}

async function optimizeFleet() {
  if (state.stops.length < 2) {
    alert('Add at least 2 stops (including depot) to optimize.');
    return;
  }

  clearRoutes();
  setLoading(true);

  const depotIndex = parseInt(document.getElementById('depotSelect').value || '0');

  const payload = {
    stops: state.stops.map(s => ({ lat: s.lat, lng: s.lng, demand: 1 })),
    vehicles: state.vehicles.map(v => ({ capacity: v.capacity, label: v.label })),
    depot_index: depotIndex,
  };

  try {
    const resp = await fetch('/optimize/fleet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(`Error: ${err.detail}`);
      return;
    }

    const data = await resp.json();
    renderFleetResult(data, depotIndex);
  } catch (e) {
    alert('Network error — is the server running?');
  } finally {
    setLoading(false);
  }
}

function renderFleetResult(data, depotIndex) {

  const stopVehicle = {};
  data.routes.forEach((route, ri) => {
    route.ordered_indices.forEach(si => {
      stopVehicle[si] = ri;
    });
  });

  state.markers.forEach((m, i) => {
    const vIdx = stopVehicle[i];
    const color = vIdx !== undefined ? VEHICLE_COLORS[vIdx % VEHICLE_COLORS.length] : '#666';
    m.setIcon(makeIcon(i, color));
  });


  data.routes.forEach((route, ri) => {
    const color = VEHICLE_COLORS[ri % VEHICLE_COLORS.length];
    route.legs.forEach(leg => {
      drawPolyline(leg.polyline, color, 4);
    });
  });


  const allCoords = data.routes.flatMap(r => r.legs.flatMap(l => l.polyline));
  if (allCoords.length) map.fitBounds(allCoords, { padding: [40, 40] });

  // Results panel
  const panel = document.getElementById('resultsPanel');
  panel.classList.remove('hidden');

  let html = `
    <div class="result-stat">
      <span>Total fleet time</span>
      <span class="val">${formatDuration(data.total_duration_seconds)}</span>
    </div>
    <div class="result-stat">
      <span>Vehicles used</span>
      <span class="val">${data.routes.length}</span>
    </div>`;

  if (data.unassigned_stops.length > 0) {
    html += `<div class="result-stat">
      <span style="color:var(--warn)">Unassigned stops</span>
      <span class="val" style="color:var(--warn)">${data.unassigned_stops.length}</span>
    </div>`;
  }

  data.routes.forEach((route, ri) => {
    const color = VEHICLE_COLORS[ri % VEHICLE_COLORS.length];
    const stopNums = route.ordered_indices.map(i => i + 1).join(' → ');
    const gmapsBtn = googleMapsButtonHTML(route.ordered_indices, `Open ${route.label || `Vehicle ${ri + 1}`} in Maps`);
    html += `
      <div class="vehicle-result-card" style="border-left-color:${color}">
        <div class="v-label" style="color:${color}">${route.label || `Vehicle ${ri + 1}`}</div>
        <div class="v-stats">${formatDuration(route.total_duration_seconds)} · ${route.total_load} units</div>
        <div class="route-order">${stopNums}</div>
        ${gmapsBtn}
      </div>`;
  });

  panel.innerHTML = html;

  if (data.used_fallback) {
    document.getElementById('fallbackWarning').classList.remove('hidden');
  }
}
