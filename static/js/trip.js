/* ── Trip Planner (TSP) ─────────────────────────────────────────────────── */

async function optimizeTrip() {
  if (state.stops.length < 2) {
    alert('Add at least 2 stops to optimize.');
    return;
  }

  clearRoutes();
  setLoading(true);

  const startIndex = parseInt(document.getElementById('startSelect').value || '0');
  const endIndex = parseInt(document.getElementById('endSelect').value || '0');

  const payload = {
    stops: state.stops.map(s => ({ lat: s.lat, lng: s.lng })),
    start_index: startIndex,
    end_index: endIndex,
  };

  try {
    const resp = await fetch('/optimize', {
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
    renderTripResult(data);
  } catch (e) {
    alert('Network error — is the server running?');
  } finally {
    setLoading(false);
  }
}

function renderTripResult(data) {

  data.legs.forEach(leg => {
    drawPolyline(leg.polyline, '#5b7fff', 4);
  });


  data.ordered_indices.forEach((stopIdx, routePos) => {
    state.markers[stopIdx].setIcon(makeIcon(stopIdx, '#5b7fff'));
  });


  const allCoords = data.legs.flatMap(l => l.polyline);
  if (allCoords.length) map.fitBounds(allCoords, { padding: [40, 40] });


  const panel = document.getElementById('resultsPanel');
  panel.classList.remove('hidden');

  const order = data.ordered_indices.map(i => i + 1).join(' → ');
  panel.innerHTML = `
    <div class="result-stat">
      <span>Total travel time</span>
      <span class="val">${formatDuration(data.total_duration_seconds)}</span>
    </div>
    <div class="result-stat">
      <span>Stops</span>
      <span class="val">${state.stops.length}</span>
    </div>
    <div class="route-order">${order}</div>
    ${googleMapsButtonHTML(data.ordered_indices)}
  `;

  if (data.used_fallback) {
    document.getElementById('fallbackWarning').classList.remove('hidden');
  }
}
