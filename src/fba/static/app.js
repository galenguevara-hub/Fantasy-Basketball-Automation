// ─── League ID Management ─────────────────────────────────────────────────────

function showLeagueInput() {
  document.getElementById('league-controls').classList.add('hidden');
  const wrap = document.getElementById('league-input-wrap');
  wrap.classList.remove('hidden');
  // Add cancel button if not already present
  if (!wrap.querySelector('.btn-link')) {
    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-link';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.onclick = cancelLeagueChange;
    wrap.appendChild(cancelBtn);
  }
  document.getElementById('league-id-input').focus();
}

function cancelLeagueChange() {
  document.getElementById('league-input-wrap').classList.add('hidden');
  document.getElementById('league-controls').classList.remove('hidden');
}

function connectLeague() {
  const input = document.getElementById('league-id-input');
  const leagueId = input.value.trim();

  if (!leagueId) {
    showToast('Please enter a league ID.', true);
    return;
  }

  if (!/^\d+$/.test(leagueId)) {
    showToast('League ID must be a number.', true);
    return;
  }

  const btn = document.getElementById('connect-btn');
  btn.disabled = true;
  btn.textContent = 'Connecting...';

  // Save the league ID
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ league_id: leagueId }),
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        showToast('League connected. Fetching standings...', false);
        // Now trigger a refresh (will open browser for login if no session)
        doRefresh(btn, 'Connect');
      } else {
        showToast('Error: ' + (data.error || 'Unknown error'), true);
        btn.disabled = false;
        btn.textContent = 'Connect';
      }
    })
    .catch(err => {
      showToast('Failed to save league: ' + err.message, true);
      btn.disabled = false;
      btn.textContent = 'Connect';
    });
}

// ─── Refresh ──────────────────────────────────────────────────────────────────

function refreshData() {
  const btn = document.getElementById('refresh-btn');
  doRefresh(btn, 'Refresh');
}

function doRefresh(btn, originalLabel) {
  btn.disabled = true;
  btn.textContent = 'Refreshing...';

  showToast('Fetching latest standings from Yahoo...', false);

  fetch('/refresh', { method: 'POST' })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        if (data.login_required) {
          showToast('Signed in and standings updated!', false);
        } else {
          showToast('Standings updated!', false);
        }
        setTimeout(() => location.reload(), 800);
      } else {
        if (data.session_expired) {
          showToast('Session expired. Refreshing will open a browser to sign in again.', true);
        } else {
          showToast('Error: ' + (data.error || 'Unknown error'), true);
        }
        btn.disabled = false;
        btn.textContent = originalLabel;
      }
    })
    .catch(err => {
      showToast('Request failed: ' + err.message, true);
      btn.disabled = false;
      btn.textContent = originalLabel;
    });
}

function showToast(message, isError) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast' + (isError ? ' error' : '');
  clearTimeout(toast._timeout);
  if (isError) {
    toast._timeout = setTimeout(() => { toast.className = 'toast hidden'; }, 5000);
  }
}

// ─── Sortable Tables ──────────────────────────────────────────────────────────

/**
 * Parse a cell's text into a sortable value.
 * "—" and empty cells always sort last regardless of direction.
 * Numbers are parsed as floats; everything else is a lowercase string.
 */
function parseCellValue(text) {
  const t = text.trim();
  if (t === '—' || t === '') return null;          // null = sort last
  // Strip trailing % so "47.6%" → 47.6
  const n = parseFloat(t.replace(/[%,]/g, ''));
  return isNaN(n) ? t.toLowerCase() : n;
}

/**
 * Sort a table by the clicked <th> column.
 * Toggles asc → desc → asc on repeated clicks of the same column.
 * "—" cells always sink to the bottom regardless of sort direction.
 */
function sortTable(th) {
  const table = th.closest('table');
  const thead = table.querySelector('thead');
  const tbody = table.querySelector('tbody');
  const ths   = Array.from(thead.querySelectorAll('th'));
  const colIdx = ths.indexOf(th);

  // Determine sort direction: first click → asc, same col again → toggle
  const currentDir = th.dataset.sortDir || '';
  const newDir = currentDir === 'asc' ? 'desc' : 'asc';

  // Clear sort state from all headers in this table
  ths.forEach(h => {
    delete h.dataset.sortDir;
    h.classList.remove('sort-asc', 'sort-desc');
  });

  th.dataset.sortDir = newDir;
  th.classList.add(newDir === 'asc' ? 'sort-asc' : 'sort-desc');

  // Collect rows and sort
  const rows = Array.from(tbody.querySelectorAll('tr'));

  rows.sort((a, b) => {
    const aText = (a.cells[colIdx] ? a.cells[colIdx].textContent : '');
    const bText = (b.cells[colIdx] ? b.cells[colIdx].textContent : '');
    const aVal  = parseCellValue(aText);
    const bVal  = parseCellValue(bText);

    // Nulls (—) always sink to the bottom
    if (aVal === null && bVal === null) return 0;
    if (aVal === null) return 1;
    if (bVal === null) return -1;

    // Compare
    let cmp;
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      cmp = aVal - bVal;
    } else {
      cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    }

    return newDir === 'asc' ? cmp : -cmp;
  });

  // Re-append sorted rows (preserves row-alt striping based on DOM position after sort)
  rows.forEach((row, i) => {
    row.classList.toggle('row-alt', i % 2 === 0);
    tbody.appendChild(row);
  });
}

/**
 * Attach sort handlers to every <th> in every <table> on the page.
 * Called once after DOM is ready.
 */
function initSortableTables() {
  document.querySelectorAll('table thead th').forEach(th => {
    th.classList.add('sortable');
    th.addEventListener('click', () => sortTable(th));
  });
}

document.addEventListener('DOMContentLoaded', initSortableTables);
