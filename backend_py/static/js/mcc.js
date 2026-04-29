(function () {
  var state = {
    connectedMcc: null,
    probe: null,
    dashboard: null,
    accounts: [],
    accountsTotal: 0,
    accountsLimit: 50,
    accountsOffset: 0,
    accountsHasMore: false,
    accountsQuery: '',
    accountSearchTimer: null,
    watchlists: [],
    defaultWatchlistId: 0,
    activeWatchlistId: 0,
    watchlistItems: [],
    watchlistTotal: 0,
    watchlistLimit: 50,
    watchlistOffset: 0,
    watchlistHasMore: false,
    watchlistQuery: '',
    watchlistSearchTimer: null,
    detailsInFlight: false,
    selectedCustomerId: '',
    briefing: [],
    activeReport: 'campaigns',
    activeRunId: '',
    activePane: 'overview',
    refreshInFlight: false,
    lastRefreshAt: 0,
    rateLimitTimer: null,
    rateLimitUntilTs: 0
  };

  function toPosInt(v, fallback) {
    var n = Number(v || 0);
    if (!isFinite(n) || n <= 0) return Number(fallback || 0);
    return Math.floor(n);
  }

  function fmtNum(v, d) {
    var n = Number(v || 0);
    if (!isFinite(n)) n = 0;
    return n.toFixed(d || 2);
  }

  function probeAllowsData(probe) {
    if (!probe) return false;
    if (probe.probe_ok) return true;
    if (probe.includes_mcc) return true;
    var accessible = Number(probe.accessible_count || 0);
    if (isFinite(accessible) && accessible > 0) return true;
    return false;
  }

  async function fetchJson(url, options) {
    var res = await fetch(url, options || {});
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      var err = new Error((data && (data.error || data.reason || data.details || data.message)) || ('http_' + res.status));
      err.status = res.status;
      err.payload = data || {};
      throw err;
    }
    return data;
  }

  function setLoading(section, isLoading) {
    if (!window.showToast) return;
    if (isLoading) window.showToast('MCC', section + ' loading...', 'info');
  }

  function setMeta() {
    var meta = document.getElementById('mccMeta');
    var probeMeta = document.getElementById('mccProbeMeta');
    if (!meta) return;
    if (!state.connectedMcc) {
      meta.textContent = 'Not connected';
      if (probeMeta) probeMeta.textContent = '';
      return;
    }
    meta.textContent = 'Connected: ' + (state.connectedMcc.name || state.connectedMcc.slug || 'MCC')
      + ' | login_customer_id: ' + (state.connectedMcc.login_customer_id || '-')
      + ' | status: ' + (state.connectedMcc.status || '-');
    if (probeMeta && state.probe) {
      var canLoad = probeAllowsData(state.probe);
      var probeLabel = canLoad ? 'probe: ok' : 'probe: pending';
      if (!canLoad && Number(state.probe.upstream_status || 0) === 429) probeLabel = 'probe: rate-limited';
      if (!canLoad && Number(state.probe.upstream_status || 0) && Number(state.probe.upstream_status || 0) !== 429) probeLabel = 'probe: not ready';
      var stale = state.probe.stale_data ? ' | stale cache' : '';
      probeMeta.textContent = probeLabel + stale + ' | accessible: ' + Number(state.probe.accessible_count || 0);
    } else if (probeMeta) {
      probeMeta.textContent = '';
    }
  }

  function fmtInt(v) {
    var n = Number(v || 0);
    if (!isFinite(n)) n = 0;
    return n.toLocaleString('en-US');
  }

  function renderDashboardSummary() {
    var connectedEl = document.getElementById('mccSummaryConnected');
    if (!connectedEl) return;
    var loginCidEl = document.getElementById('mccSummaryLoginCid');
    var clientsEl = document.getElementById('mccSummaryClients');
    var tokensEl = document.getElementById('mccSummaryTokens');
    var costEl = document.getElementById('mccSummaryCost');
    var cyclesEl = document.getElementById('mccSummaryCycles');
    var budgetEl = document.getElementById('mccSummaryBudget');
    var policyEl = document.getElementById('mccSummaryPolicy');
    var protocolEl = document.getElementById('mccSummaryProtocol');
    var flowsEl = document.getElementById('mccRecommendedFlows');

    if (!state.dashboard) {
      connectedEl.textContent = state.connectedMcc ? (state.connectedMcc.name || state.connectedMcc.slug || 'Connected') : 'Not connected';
      if (loginCidEl) loginCidEl.textContent = state.connectedMcc ? ('login_customer_id: ' + (state.connectedMcc.login_customer_id || '-')) : '-';
      return;
    }

    var payload = state.dashboard || {};
    var mcc = payload.mcc || state.connectedMcc || {};
    var dash = payload.dashboard || {};
    var summary = dash.summary || {};
    var tokens = payload.tokens || {};
    var costEstimate = payload.cost_estimate || {};
    var capabilities = payload.capabilities || {};
    var adsApi = capabilities.google_ads_api || {};
    var flows = Array.isArray(payload.recommended_templates) ? payload.recommended_templates : [];

    connectedEl.textContent = mcc.name || mcc.slug || 'Connected';
    if (loginCidEl) loginCidEl.textContent = 'login_customer_id: ' + (mcc.login_customer_id || '-');
    if (clientsEl) clientsEl.textContent = String(summary.clients_active || 0) + ' / ' + String(summary.clients_total || 0);
    if (tokensEl) tokensEl.textContent = fmtInt(tokens.total_tokens || 0);
    if (costEl) costEl.textContent = '$' + fmtNum(tokens.total_cost_usd || 0, 6);
    if (cyclesEl) cyclesEl.textContent = String(summary.refresh_cycles_today || 0);
    if (budgetEl) {
      var opsRem = (((costEstimate || {}).budget || {}).operations_remaining);
      budgetEl.textContent = 'ops left: ' + fmtInt(opsRem || 0);
    }
    if (policyEl) policyEl.textContent = adsApi.can_mutate ? 'Read / Write' : 'Read-only';
    if (protocolEl) {
      var protocol = payload.protocol || {};
      protocolEl.textContent = 'protocol: ' + String(protocol.name || 'cblm.mcc.v1');
    }
    if (flowsEl) {
      flowsEl.innerHTML = '';
      if (!flows.length) {
        flowsEl.innerHTML = '<span class="text-muted">No flow recommendations loaded.</span>';
      } else {
        flows.forEach(function (flow) {
          var a = document.createElement('a');
          a.className = 'btn btn-sm btn-outline-info';
          a.href = String(flow.url || '/orchestrator');
          a.textContent = String(flow.name || flow.id || 'Flow');
          a.title = String(flow.description || '');
          flowsEl.appendChild(a);
        });
      }
    }
  }

  async function loadDashboardSummary() {
    if (!state.connectedMcc) {
      state.dashboard = null;
      renderDashboardSummary();
      return null;
    }
    var endpoint = String(window.MCC_DASHBOARD_API_PATH || '/api/mcc/dashboard');
    var data = await fetchJson(endpoint);
    state.dashboard = data || null;
    renderDashboardSummary();
    return state.dashboard;
  }

  function toggleActions(enabled) {
    var refreshBtn = document.getElementById('mccRefreshBtn');
    var exportBtn = document.getElementById('mccExportBtn');
    var briefBtn = document.getElementById('mccRunBriefBtn');
    if (refreshBtn) refreshBtn.disabled = !enabled || !!state.refreshInFlight;
    if (exportBtn) exportBtn.disabled = !enabled || !!state.refreshInFlight;
    if (briefBtn) briefBtn.disabled = !enabled || !!state.refreshInFlight;
  }

  function hideRateLimitBanner() {
    var el = document.getElementById('mccRateLimitBanner');
    if (el) el.classList.add('d-none');
    if (state.rateLimitTimer) {
      clearInterval(state.rateLimitTimer);
      state.rateLimitTimer = null;
    }
    state.rateLimitUntilTs = 0;
  }

  function showRateLimitBanner(retryAfterSec) {
    var seconds = Math.max(1, Number(retryAfterSec || 20));
    state.rateLimitUntilTs = Date.now() + seconds * 1000;
    var el = document.getElementById('mccRateLimitBanner');
    var txt = document.getElementById('mccRateLimitText');
    if (!el || !txt) return;
    el.classList.remove('d-none');

    function renderTick() {
      var left = Math.max(0, Math.ceil((state.rateLimitUntilTs - Date.now()) / 1000));
      txt.textContent = 'Google Ads API rate-limited (429). Retrying in ' + left + 's…';
    }

    renderTick();
    if (state.rateLimitTimer) clearInterval(state.rateLimitTimer);
    state.rateLimitTimer = setInterval(renderTick, 1000);
  }

  function activeWatchlistId() {
    return toPosInt(state.activeWatchlistId, toPosInt(state.defaultWatchlistId, 0));
  }

  function selectedWatchlistIdForAdd() {
    var sel = document.getElementById('mccAccountWatchlistSelect');
    if (!sel) return activeWatchlistId();
    return toPosInt(sel.value, activeWatchlistId());
  }

  function bumpWatchlistCount(watchlistId, delta) {
    var targetId = toPosInt(watchlistId, 0);
    if (!targetId || !Array.isArray(state.watchlists)) return;
    state.watchlists = state.watchlists.map(function (wl) {
      if (toPosInt(wl.id, 0) !== targetId) return wl;
      var next = Number(wl.count || 0) + Number(delta || 0);
      wl.count = Math.max(0, next);
      return wl;
    });
  }

  function setPane(pane) {
    var next = String(pane || 'overview').toLowerCase() === 'watchlist' ? 'watchlist' : 'overview';
    state.activePane = next;
    document.querySelectorAll('#mccMainTabs [data-pane]').forEach(function (btn) {
      var isActive = String(btn.getAttribute('data-pane') || '') === next;
      btn.classList.toggle('active', isActive);
    });
    var overview = document.getElementById('mccPaneOverview');
    var watchlist = document.getElementById('mccPaneWatchlist');
    if (overview) overview.classList.toggle('d-none', next !== 'overview');
    if (watchlist) watchlist.classList.toggle('d-none', next !== 'watchlist');
  }

  function renderWatchlistSelectors() {
    var accountSelect = document.getElementById('mccAccountWatchlistSelect');
    var watchlistSelect = document.getElementById('mccWatchlistSelect');
    var oldAccountSel = accountSelect ? String(accountSelect.value || '') : '';
    var oldWatchSel = watchlistSelect ? String(watchlistSelect.value || '') : '';
    var desired = String(activeWatchlistId() || '');

    function fillSelect(selectEl, preferred) {
      if (!selectEl) return;
      selectEl.innerHTML = '';
      var rows = state.watchlists || [];
      if (!rows.length) {
        var optEmpty = document.createElement('option');
        optEmpty.value = '';
        optEmpty.textContent = 'No watchlists';
        selectEl.appendChild(optEmpty);
        selectEl.disabled = true;
        return;
      }
      rows.forEach(function (wl) {
        var opt = document.createElement('option');
        opt.value = String(wl.id || '');
        opt.textContent = String(wl.name || 'Watchlist') + ' (' + Number(wl.count || 0) + ')';
        selectEl.appendChild(opt);
      });
      selectEl.disabled = false;
      var tryValues = [preferred, oldAccountSel, oldWatchSel, desired];
      var selected = '';
      tryValues.forEach(function (candidate) {
        if (selected) return;
        var c = String(candidate || '');
        if (!c) return;
        if (Array.from(selectEl.options).some(function (o) { return String(o.value) === c; })) selected = c;
      });
      if (!selected) {
        selected = String(toPosInt(state.defaultWatchlistId, toPosInt((rows[0] || {}).id, 0)) || '');
      }
      selectEl.value = selected;
    }

    fillSelect(accountSelect, oldAccountSel);
    fillSelect(watchlistSelect, oldWatchSel || desired);
    if (watchlistSelect && !watchlistSelect.disabled) {
      state.activeWatchlistId = toPosInt(watchlistSelect.value, state.activeWatchlistId);
    }
    var nameInput = document.getElementById('mccWatchlistNameInput');
    if (nameInput && document.activeElement !== nameInput) {
      var current = (state.watchlists || []).find(function (wl) { return toPosInt(wl.id, 0) === activeWatchlistId(); });
      nameInput.value = current ? String(current.name || '') : '';
    }
  }

  function renderWatchlistItems() {
    var root = document.getElementById('mccWatchlistItems');
    var count = document.getElementById('mccWatchlistCount');
    var moreBtn = document.getElementById('mccWatchlistMoreBtn');
    if (!root) return;
    root.innerHTML = '';
    var loaded = Number((state.watchlistItems || []).length || 0);
    var total = Number(state.watchlistTotal || loaded || 0);
    if (count) count.textContent = total > loaded ? (String(loaded) + '/' + String(total)) : String(total);
    var frag = document.createDocumentFragment();
    (state.watchlistItems || []).forEach(function (it) {
      var row = document.createElement('div');
      row.className = 'list-group-item bg-dark text-light border-secondary d-flex justify-content-between align-items-center';
      var title = (it.descriptive_name || ('Account ' + (it.customer_id || ''))).trim();
      row.innerHTML = '<div><div class="fw-semibold">' + title + '</div><small class="text-muted">' + (it.customer_id || '') + '</small></div>'
        + '<button class="btn btn-sm btn-outline-danger" data-remove-cid="' + (it.customer_id || '') + '">Remove</button>';
      var btn = row.querySelector('button[data-remove-cid]');
      if (btn) {
        btn.addEventListener('click', function () {
          removeFromActiveWatchlist(btn.getAttribute('data-remove-cid') || '').catch(handleApiError);
        });
      }
      frag.appendChild(row);
    });
    root.appendChild(frag);
    if (moreBtn) moreBtn.classList.toggle('d-none', !state.watchlistHasMore);
  }

  async function loadWatchlists(opts) {
    opts = opts || {};
    var prevActive = activeWatchlistId();
    var data = await fetchJson('/api/mcc/watchlists');
    var rows = Array.isArray(data.items) ? data.items : [];
    state.watchlists = rows.map(function (r) {
      return {
        id: toPosInt(r.id, 0),
        name: String(r.name || ''),
        count: Number(r.count || 0)
      };
    }).filter(function (r) { return r.id > 0; });
    state.defaultWatchlistId = toPosInt(data.default_id, 0);
    var wanted = toPosInt(state.activeWatchlistId, 0);
    if (!wanted || !state.watchlists.some(function (wl) { return wl.id === wanted; })) {
      wanted = toPosInt(state.defaultWatchlistId, toPosInt((state.watchlists[0] || {}).id, 0));
    }
    state.activeWatchlistId = wanted;
    if (toPosInt(prevActive, 0) !== toPosInt(state.activeWatchlistId, 0)) {
      state.briefing = [];
      renderBriefing();
    }
    renderWatchlistSelectors();
    if (opts.loadItems) await loadWatchlistItems({ reset: true });
  }

  async function loadWatchlistItems(opts) {
    opts = opts || {};
    var watchlistId = activeWatchlistId();
    if (!watchlistId) {
      state.watchlistItems = [];
      state.watchlistTotal = 0;
      state.watchlistHasMore = false;
      renderWatchlistItems();
      return;
    }
    var append = !!opts.append;
    if (typeof opts.query === 'string') {
      state.watchlistQuery = String(opts.query || '').trim();
      append = false;
    }
    var offset = append ? Number((state.watchlistItems || []).length || 0) : 0;
    var qs = new URLSearchParams();
    qs.set('limit', String(toPosInt(state.watchlistLimit, 50)));
    qs.set('offset', String(Math.max(0, offset)));
    if (state.watchlistQuery) qs.set('q', state.watchlistQuery);
    var data = await fetchJson('/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)) + '/items?' + qs.toString());
    var rows = Array.isArray(data.items) ? data.items : [];
    if (append) state.watchlistItems = (state.watchlistItems || []).concat(rows);
    else state.watchlistItems = rows;
    state.watchlistTotal = Number(data.total || state.watchlistItems.length || 0);
    state.watchlistOffset = Number(data.offset || offset || 0);
    state.watchlistHasMore = !!data.has_more || (state.watchlistItems.length < state.watchlistTotal);
    renderWatchlistItems();
  }

  async function addAccountToWatchlist(account) {
    var row = account || {};
    var customerId = String(row.customer_id || '').trim();
    if (!customerId) return;
    var watchlistId = selectedWatchlistIdForAdd();
    if (!watchlistId) {
      if (window.showToast) window.showToast('Watchlist', 'No watchlist selected', 'error');
      return;
    }
    var payload = {
      customer_id: customerId,
      descriptive_name: String(row.account_name || ''),
      is_manager: false
    };
    var data = await fetchJson('/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)) + '/items', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    var created = !!(data && data.created);
    if (created) bumpWatchlistCount(watchlistId, 1);
    if (toPosInt(watchlistId, 0) === activeWatchlistId()) {
      var item = (data && data.item) ? data.item : payload;
      var exists = (state.watchlistItems || []).some(function (it) { return String(it.customer_id || '') === String(item.customer_id || ''); });
      if (!exists && created) {
        state.watchlistItems = [item].concat(state.watchlistItems || []);
        state.watchlistTotal = Number(state.watchlistTotal || 0) + 1;
      }
      renderWatchlistItems();
    }
    renderWatchlistSelectors();
    if (window.showToast) window.showToast('Watchlist', created ? 'Added' : 'Already exists', created ? 'success' : 'info');
  }

  async function removeFromActiveWatchlist(customerId) {
    var cid = String(customerId || '').trim();
    if (!cid) return;
    var watchlistId = activeWatchlistId();
    if (!watchlistId) return;
    var data = await fetchJson('/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)) + '/items/' + encodeURIComponent(cid), {
      method: 'DELETE'
    });
    if (data && data.deleted) {
      bumpWatchlistCount(watchlistId, -1);
      state.watchlistItems = (state.watchlistItems || []).filter(function (it) { return String(it.customer_id || '') !== cid; });
      state.watchlistTotal = Math.max(0, Number(state.watchlistTotal || 0) - 1);
      renderWatchlistItems();
      renderWatchlistSelectors();
      if (window.showToast) window.showToast('Watchlist', 'Removed', 'success');
    }
  }

  async function createWatchlist(name) {
    var cleaned = String(name || '').trim();
    if (!cleaned) return;
    await fetchJson('/api/mcc/watchlists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: cleaned })
    });
    await loadWatchlists({ loadItems: false });
    var created = (state.watchlists || []).find(function (wl) { return String(wl.name || '') === cleaned; });
    if (created) state.activeWatchlistId = toPosInt(created.id, state.activeWatchlistId);
    renderWatchlistSelectors();
    await loadWatchlistItems({ reset: true });
    if (window.showToast) window.showToast('Watchlist', 'Created', 'success');
  }

  async function renameActiveWatchlist(name) {
    var cleaned = String(name || '').trim();
    var watchlistId = activeWatchlistId();
    if (!watchlistId || !cleaned) return;
    await fetchJson('/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: cleaned })
    });
    await loadWatchlists({ loadItems: false });
    if (window.showToast) window.showToast('Watchlist', 'Renamed', 'success');
  }

  async function deleteActiveWatchlist() {
    var watchlistId = activeWatchlistId();
    if (!watchlistId) return;
    await fetchJson('/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)), {
      method: 'DELETE'
    });
    await loadWatchlists({ loadItems: true });
    if (window.showToast) window.showToast('Watchlist', 'Deleted', 'success');
  }

  function renderAccounts() {
    var root = document.getElementById('mccAccounts');
    var count = document.getElementById('mccAccountCount');
    var moreBtn = document.getElementById('mccAccountsMoreBtn');
    if (!root) return;
    var loaded = Number((state.accounts || []).length || 0);
    var total = Number(state.accountsTotal || loaded || 0);
    if (count) count.textContent = total > loaded ? (String(loaded) + '/' + String(total)) : String(loaded);
    root.innerHTML = '';
    var frag = document.createDocumentFragment();
    (state.accounts || []).forEach(function (a) {
      var row = document.createElement('div');
      row.className = 'list-group-item bg-dark text-light border-secondary p-1';

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-sm btn-outline-secondary text-start flex-grow-1';
      if (String(a.customer_id) === String(state.selectedCustomerId)) {
        btn.classList.remove('btn-outline-secondary');
        btn.classList.add('btn-info');
      }
      btn.textContent = (a.account_name || ('Account ' + a.customer_id)) + ' (' + a.customer_id + ')';
      btn.addEventListener('click', function () {
        state.selectedCustomerId = String(a.customer_id || '');
        renderAccounts();
        loadSelectedAccountDetails().catch(handleApiError);
      });

      var addBtn = document.createElement('button');
      addBtn.type = 'button';
      addBtn.className = 'btn btn-sm btn-outline-success';
      addBtn.textContent = 'Add';
      addBtn.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        addAccountToWatchlist(a).catch(handleApiError);
      });

      var wrap = document.createElement('div');
      wrap.className = 'd-flex gap-2';
      wrap.appendChild(btn);
      wrap.appendChild(addBtn);
      row.appendChild(wrap);
      frag.appendChild(row);
    });
    root.appendChild(frag);
    if (moreBtn) {
      moreBtn.classList.toggle('d-none', !state.accountsHasMore);
      moreBtn.disabled = state.refreshInFlight;
    }
  }

  function renderBriefing() {
    var body = document.getElementById('mccBriefingBody');
    if (!body) return;
    body.innerHTML = '';
    function toFlags(item) {
      if (!item) return [];
      if (Array.isArray(item.flags)) return item.flags;
      if (typeof item.flags === 'string' && item.flags.trim()) return item.flags.split('|').map(function (x) { return String(x || '').trim(); }).filter(Boolean);
      return [];
    }
    function severity(item) {
      var flags = toFlags(item);
      var s = 0;
      if (flags.indexOf('FETCH_ERROR') >= 0) s += 1000;
      if (flags.indexOf('ROAS_DROP') >= 0) s += 100;
      if (flags.indexOf('SPEND_SPIKE') >= 0) s += 50;
      if (flags.indexOf('NO_CONVERSIONS') >= 0) s += 25;
      return s;
    }
    var rows = (state.briefing || []).slice().sort(function (a, b) {
      var sa = severity(a);
      var sb = severity(b);
      if (sb !== sa) return sb - sa;
      var da = Number((((a || {}).delta || {}).roas_7_vs_30_pct) || 0);
      var db = Number((((b || {}).delta || {}).roas_7_vs_30_pct) || 0);
      return da - db;
    });
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="6" class="text-muted">Run briefing for active watchlist.</td></tr>';
      return;
    }
    rows.forEach(function (r) {
      var m7 = ((r || {}).metrics || {})['7'] || {};
      var m30 = ((r || {}).metrics || {})['30'] || {};
      var delta = (r || {}).delta || {};
      var flags = toFlags(r);
      var badgeHtml = flags.map(function (f) {
        var cls = 'bg-secondary';
        if (f === 'ROAS_DROP') cls = 'bg-danger';
        else if (f === 'SPEND_SPIKE') cls = 'bg-warning text-dark';
        else if (f === 'NO_CONVERSIONS') cls = 'bg-info text-dark';
        else if (f === 'FETCH_ERROR') cls = 'bg-dark border border-danger';
        return '<span class="badge ' + cls + ' me-1">' + String(f) + '</span>';
      }).join('');
      var label = (r.descriptive_name || ('Account ' + (r.customer_id || ''))).trim();
      var tr = document.createElement('tr');
      tr.innerHTML = [
        '<td><div>' + label + '</div><small class="text-muted">' + (r.customer_id || '') + '</small></td>',
        '<td>' + fmtNum(m7.roas, 2) + '</td>',
        '<td>' + fmtNum(m30.roas, 2) + '</td>',
        '<td>' + fmtNum(delta.roas_7_vs_30_pct, 1) + '%</td>',
        '<td>' + fmtNum(delta.cost_7_vs_30_pct, 1) + '%</td>',
        '<td>' + (badgeHtml || '<small class="text-muted">-</small>') + '</td>'
      ].join('');
      body.appendChild(tr);
    });
  }

  function renderRuns(rows) {
    var body = document.getElementById('mccRunsBody');
    if (!body) return;
    body.innerHTML = '';
    function badgeHtml(item) {
      var label = String(item.report || '');
      var ok = Number(item.ok || 0);
      var fail = Number(item.fail || 0);
      var rowsCount = Number(item.rows || 0);
      var cls = fail > 0 ? 'bg-danger' : 'bg-success';
      return '<span class="badge ' + cls + ' me-1 mb-1">' + label + ' ok:' + ok + ' fail:' + fail + ' rows:' + rowsCount + '</span>';
    }
    (rows || []).forEach(function (r) {
      var tr = document.createElement('tr');
      var reports = Array.isArray(r.report_badges) ? r.report_badges.map(badgeHtml).join('') : '';
      tr.innerHTML = [
        '<td><code>' + (r.run_id || '') + '</code></td>',
        '<td>' + (r.mcc_slug || '') + '</td>',
        '<td>' + reports + '</td>',
        '<td>' + (r.status || '') + '</td>',
        '<td>' + (r.account_count || 0) + '</td>',
        '<td>' + (r.failure_count || 0) + '</td>',
        '<td>' + (r.duration_ms || 0) + '</td>',
        '<td>' + (r.started_at || '') + '</td>',
        '<td><button class="btn btn-sm btn-outline-info" data-run-id="' + (r.run_id || '') + '">View run events</button></td>'
      ].join('');
      var btn = tr.querySelector('button[data-run-id]');
      if (btn) {
        btn.addEventListener('click', function () {
          openEventsModal(btn.getAttribute('data-run-id') || '');
        });
      }
      body.appendChild(tr);
    });
  }

  function renderDrill(reportName, rows) {
    var account = (state.accounts || []).find(function (a) { return String(a.customer_id) === String(state.selectedCustomerId); });
    var title = document.getElementById('mccDrillTitle');
    var meta = document.getElementById('mccDrillMeta');
    if (title) title.textContent = 'Account Drill-down: ' + (account ? account.account_name : '-');
    if (meta) meta.textContent = 'report: ' + reportName + ' | rows: ' + ((rows || []).length);

    var head = document.getElementById('mccDrillHead');
    var body = document.getElementById('mccDrillBody');
    if (!head || !body) return;
    body.innerHTML = '';
    var first = (rows || [])[0] || {};
    var keys = Object.keys(first).filter(function (k) {
      return ['run_id', 'run_utc', 'mcc_slug', 'login_customer_id', 'customer_id', 'account_name'].indexOf(k) === -1;
    }).slice(0, 9);
    head.innerHTML = '<tr>' + keys.map(function (k) { return '<th>' + k + '</th>'; }).join('') + '</tr>';
    (rows || []).slice(0, 100).forEach(function (row) {
      var tr = document.createElement('tr');
      tr.innerHTML = keys.map(function (k) { return '<td>' + String(row[k] == null ? '' : row[k]) + '</td>'; }).join('');
      body.appendChild(tr);
    });
    if (!(rows || []).length) {
      body.innerHTML = '<tr><td class="text-muted">not available</td></tr>';
    }
  }

  function clearSelectedAccountDetails() {
    state.briefing = [];
    renderBriefing();
    renderDrill(state.activeReport, []);
  }

  async function loadRegistry() {
    var data = await fetchJson('/api/mcc/registry');
    state.connectedMcc = data.connected_mcc || window.MCC_CONNECTED || null;
    setMeta();
    var input = document.getElementById('mccLoginCustomerId');
    if (input && state.connectedMcc && state.connectedMcc.login_customer_id) {
      input.value = state.connectedMcc.login_customer_id;
    }
  }

  async function loadAccounts(opts) {
    if (!state.connectedMcc) return;
    opts = opts || {};
    var append = !!opts.append;
    if (typeof opts.query === 'string') {
      state.accountsQuery = String(opts.query || '').trim();
      append = false;
    }
    var offset = append ? Number((state.accounts || []).length || 0) : 0;
    var limit = Number(state.accountsLimit || 50);
    var qs = new URLSearchParams();
    qs.set('limit', String(limit));
    qs.set('offset', String(offset));
    if (state.accountsQuery) qs.set('q', state.accountsQuery);
    var endpoint = '/api/mcc/accounts?' + qs.toString();
    var data = await fetchJson(endpoint);
    var rows = [];
    if (Array.isArray(data.accounts)) rows = data.accounts;
    else if (Array.isArray(data.rows)) rows = data.rows;
    else if (Array.isArray(data)) rows = data;
    if (append) state.accounts = (state.accounts || []).concat(rows || []);
    else state.accounts = rows || [];
    state.accountsTotal = Number(data.total || state.accounts.length || 0);
    state.accountsOffset = Number(data.offset || offset || 0);
    state.accountsHasMore = !!data.has_more || (state.accounts.length < state.accountsTotal);
    if (data && data.gateway && data.gateway.stale && window.showToast) {
      window.showToast('MCC', 'Using stale cached accounts while upstream is rate-limited', 'info');
    }
    try {
      console.info('mcc.loadAccounts', {
        endpoint: endpoint,
        mcc: state.connectedMcc ? state.connectedMcc.login_customer_id : null,
        count: state.accounts.length,
        total: state.accountsTotal,
        has_more: state.accountsHasMore,
        query: state.accountsQuery,
        gateway: data.gateway || null,
        diagnostic: data.diagnostic || null
      });
    } catch (_e) {}
    if (state.selectedCustomerId && !(state.accounts || []).some(function (a) { return String(a.customer_id || '') === String(state.selectedCustomerId); })) {
      state.selectedCustomerId = '';
      clearSelectedAccountDetails();
    }
    if (!state.accounts.length) {
      state.selectedCustomerId = '';
      clearSelectedAccountDetails();
    }
    renderAccounts();
  }

  async function loadProbe() {
    if (!state.connectedMcc) return null;
    var data = await fetchJson('/api/mcc/probe_access');
    state.probe = data || null;
    if (state.probe && state.probe.stale_data && window.showToast) {
      window.showToast('MCC', 'Using stale probe cache (upstream rate-limited)', 'info');
    }
    setMeta();
    return state.probe;
  }

  async function loadBriefing(opts) {
    if (!state.connectedMcc) return;
    opts = opts || {};
    var watchlistId = activeWatchlistId();
    if (!watchlistId) {
      state.briefing = [];
      renderBriefing();
      return;
    }
    var force = !!opts.force;
    var runBtn = document.getElementById('mccRunBriefBtn');
    var originalLabel = runBtn ? String(runBtn.textContent || 'Run Brief (7/30)') : 'Run Brief (7/30)';
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Running...';
    }
    try {
      var url = '/api/mcc/watchlists/' + encodeURIComponent(String(watchlistId)) + '/brief?window=7,30';
      if (force) url += '&force=1';
      var data = await fetchJson(url, { method: 'POST' });
      state.briefing = data.items || [];
      renderBriefing();
      var stats = data.stats || {};
      if (window.showToast) {
        window.showToast(
          'Briefing',
          'Done: ' + Number(stats.accounts_ok || 0) + ' ok / ' + Number(stats.accounts_failed || 0) + ' failed',
          'success'
        );
      }
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = originalLabel || 'Run Brief (7/30)';
      }
    }
  }

  async function loadRuns() {
    var data = await fetchJson('/api/mcc/runs?limit=20');
    renderRuns(data.runs || []);
    return data.runs || [];
  }

  async function loadReport(reportName) {
    if (!state.connectedMcc || !state.selectedCustomerId) return;
    state.activeReport = reportName || state.activeReport;
    setLoading('Report ' + state.activeReport, true);
    try {
      var url = '/api/mcc/reports/' + encodeURIComponent(state.activeReport)
        + '?window=30&customer_id=' + encodeURIComponent(state.selectedCustomerId);
      var data = await fetchJson(url);
      renderDrill(state.activeReport, data.rows || []);
    } finally {
      setLoading('Report ' + state.activeReport, false);
    }
  }

  async function loadSelectedAccountDetails() {
    if (!state.selectedCustomerId || state.detailsInFlight) return;
    state.detailsInFlight = true;
    try {
      await loadReport(state.activeReport);
    } finally {
      state.detailsInFlight = false;
    }
  }

  async function connectMcc(loginCustomerId) {
    var data = await fetchJson('/api/mcc/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ login_customer_id: loginCustomerId })
    });
    state.connectedMcc = data.mcc || null;
    state.probe = null;
    state.accounts = [];
    state.accountsTotal = 0;
    state.accountsOffset = 0;
    state.accountsHasMore = false;
    state.accountsQuery = '';
    state.selectedCustomerId = '';
    state.dashboard = null;
    clearSelectedAccountDetails();
    var searchInput = document.getElementById('mccAccountSearch');
    if (searchInput) searchInput.value = '';
    setMeta();
    toggleActions(!!state.connectedMcc);
    await refreshAll(true);
    if (window.showToast) window.showToast('MCC', 'Connected', 'success');
  }

  async function exportCurrent() {
    if (!state.connectedMcc) return;
    setLoading('Export', true);
    var data = await fetchJson('/api/mcc/export/sheets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    if (window.showToast) {
      if (data.mode === 'sheets') window.showToast('MCC export', 'Sheets export complete', 'success');
      else window.showToast('MCC export', 'Artifact export complete', 'success');
    }
    await loadRuns();
    setLoading('Export', false);
  }

  async function openEventsModal(runId) {
    if (!runId) return;
    state.activeRunId = runId;
    var label = document.getElementById('mccEventsRunId');
    if (label) label.textContent = runId;
    await loadEvents(runId);
    var modalEl = document.getElementById('mccEventsModal');
    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
      var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }

  async function openLatestRunEvents() {
    var runs = await loadRuns();
    if (runs && runs.length && runs[0].run_id) {
      await openEventsModal(runs[0].run_id);
    }
  }

  async function loadEvents(runId) {
    var stageSel = document.getElementById('mccEventsStageFilter');
    var stage = stageSel ? String(stageSel.value || '') : '';
    var qs = stage ? ('?limit=20&stage=' + encodeURIComponent(stage)) : '?limit=20';
    var data = await fetchJson('/api/mcc/runs/' + encodeURIComponent(runId) + '/events' + qs);
    var body = document.getElementById('mccEventsBody');
    if (!body) return;
    body.innerHTML = '';
    (data.events || []).forEach(function (ev) {
      var tr = document.createElement('tr');
      tr.innerHTML = [
        '<td>' + (ev.stage || '') + '</td>',
        '<td>' + (ev.status || '') + '</td>',
        '<td>' + (ev.customer_id || '') + '</td>',
        '<td><small>' + String(ev.message || '') + '</small></td>',
        '<td>' + (ev.duration_ms || 0) + '</td>',
        '<td>' + (ev.created_at || '') + '</td>'
      ].join('');
      body.appendChild(tr);
    });
  }

  function handleApiError(err) {
    var payload = err && err.payload ? err.payload : {};
    if ((payload.code || '') === 'UPSTREAM_RATE_LIMIT' || err.status === 429) {
      var retryAfter = Number(payload.retry_after_s || payload.retry_after || 20);
      showRateLimitBanner(retryAfter);
      if (window.showToast) window.showToast('MCC', 'Google Ads API rate-limited (429)', 'error');
      return;
    }
    hideRateLimitBanner();
    if (window.showToast) window.showToast('MCC', String(err.message || err), 'error');
  }

  async function refreshAll(force) {
    if (!state.connectedMcc) return;
    var now = Date.now();
    if (state.rateLimitUntilTs && now < state.rateLimitUntilTs) {
      var left = Math.max(1, Math.ceil((state.rateLimitUntilTs - now) / 1000));
      if (window.showToast) window.showToast('MCC', 'Rate limit active. Retry in ' + left + 's', 'info');
      return;
    }
    if (!force && (now - state.lastRefreshAt) < 2500) return;
    if (state.refreshInFlight) return;
    state.refreshInFlight = true;
    state.lastRefreshAt = now;
    toggleActions(!!state.connectedMcc);
    try {
      await loadProbe();
      if (!probeAllowsData(state.probe)) {
        state.accounts = [];
        state.accountsTotal = 0;
        state.accountsHasMore = false;
        renderAccounts();
        clearSelectedAccountDetails();
        await loadRuns();
        return;
      }
      await loadAccounts({ reset: true });
      await loadRuns();
      await loadDashboardSummary();
      hideRateLimitBanner();
    } finally {
      state.refreshInFlight = false;
      toggleActions(!!state.connectedMcc);
    }
  }

  async function boot() {
    try {
      await loadRegistry();
      await loadWatchlists({ loadItems: true });
      toggleActions(!!state.connectedMcc);
      await loadRuns();
      renderDashboardSummary();
      if (!state.connectedMcc) return;
      await loadDashboardSummary();
      await refreshAll(true);
    } catch (err) {
      handleApiError(err);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var connectBtn = document.getElementById('mccConnectBtn');
    var input = document.getElementById('mccLoginCustomerId');
    if (connectBtn && input) {
      connectBtn.addEventListener('click', function () {
        if (state.refreshInFlight) return;
        var value = String(input.value || '').trim();
        if (!value) return;
        connectMcc(value).catch(handleApiError);
      });
    }

    var refreshBtn = document.getElementById('mccRefreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () {
        refreshAll(false).catch(handleApiError);
      });
    }

    var accountSearchInput = document.getElementById('mccAccountSearch');
    var accountSearchBtn = document.getElementById('mccAccountSearchBtn');
    var accountMoreBtn = document.getElementById('mccAccountsMoreBtn');
    var accountWatchlistSelect = document.getElementById('mccAccountWatchlistSelect');
    var accountAddSelectedBtn = document.getElementById('mccAccountAddSelectedBtn');
    function triggerAccountSearch(immediate) {
      if (!accountSearchInput) return;
      var nextQuery = String(accountSearchInput.value || '').trim();
      if (state.accountSearchTimer) {
        clearTimeout(state.accountSearchTimer);
        state.accountSearchTimer = null;
      }
      function runSearch() {
        loadAccounts({ query: nextQuery, reset: true }).catch(handleApiError);
      }
      if (immediate) runSearch();
      else state.accountSearchTimer = setTimeout(runSearch, 300);
    }
    if (accountSearchInput) {
      accountSearchInput.addEventListener('input', function () {
        triggerAccountSearch(false);
      });
      accountSearchInput.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          triggerAccountSearch(true);
        }
      });
    }
    if (accountSearchBtn) {
      accountSearchBtn.addEventListener('click', function () {
        triggerAccountSearch(true);
      });
    }
    if (accountMoreBtn) {
      accountMoreBtn.addEventListener('click', function () {
        if (state.refreshInFlight || !state.accountsHasMore) return;
        loadAccounts({ append: true }).catch(handleApiError);
      });
    }
    if (accountWatchlistSelect) {
      accountWatchlistSelect.addEventListener('change', function () {
        var next = toPosInt(accountWatchlistSelect.value, activeWatchlistId());
        if (!next) return;
        state.activeWatchlistId = next;
        renderWatchlistSelectors();
        state.briefing = [];
        renderBriefing();
      });
    }
    if (accountAddSelectedBtn) {
      accountAddSelectedBtn.addEventListener('click', function () {
        if (!state.selectedCustomerId) {
          if (window.showToast) window.showToast('Watchlist', 'Select an account first', 'info');
          return;
        }
        var account = (state.accounts || []).find(function (a) { return String(a.customer_id || '') === String(state.selectedCustomerId || ''); });
        if (!account) {
          if (window.showToast) window.showToast('Watchlist', 'Account not found in current page', 'error');
          return;
        }
        addAccountToWatchlist(account).catch(handleApiError);
      });
    }

    var retryBtn = document.getElementById('mccRetryBtn');
    if (retryBtn) {
      retryBtn.addEventListener('click', function () {
        refreshAll(true).catch(handleApiError);
      });
    }

    var viewRunsBtn = document.getElementById('mccViewRunsBtn');
    if (viewRunsBtn) {
      viewRunsBtn.addEventListener('click', function () {
        openLatestRunEvents().catch(handleApiError);
      });
    }

    var exportBtn = document.getElementById('mccExportBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', function () { exportCurrent().catch(handleApiError); });
    }
    var runBriefBtn = document.getElementById('mccRunBriefBtn');
    if (runBriefBtn) {
      runBriefBtn.addEventListener('click', function () {
        loadBriefing({ force: false }).catch(handleApiError);
      });
    }

    document.querySelectorAll('#mccMainTabs [data-pane]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var pane = String(btn.getAttribute('data-pane') || 'overview');
        setPane(pane);
        if (pane === 'watchlist') loadWatchlistItems({ reset: true }).catch(handleApiError);
      });
    });

    document.querySelectorAll('#mccReportTabs [data-report]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('#mccReportTabs .nav-link').forEach(function (x) { x.classList.remove('active'); });
        btn.classList.add('active');
        if (!state.selectedCustomerId) return;
        loadReport(btn.getAttribute('data-report')).catch(handleApiError);
      });
    });

    var stageFilter = document.getElementById('mccEventsStageFilter');
    if (stageFilter) {
      stageFilter.addEventListener('change', function () {
        if (state.activeRunId) loadEvents(state.activeRunId).catch(handleApiError);
      });
    }

    var watchlistSelect = document.getElementById('mccWatchlistSelect');
    var watchlistSearchInput = document.getElementById('mccWatchlistSearch');
    var watchlistSearchBtn = document.getElementById('mccWatchlistSearchBtn');
    var watchlistMoreBtn = document.getElementById('mccWatchlistMoreBtn');
    var watchlistNameInput = document.getElementById('mccWatchlistNameInput');
    var watchlistCreateBtn = document.getElementById('mccWatchlistCreateBtn');
    var watchlistRenameBtn = document.getElementById('mccWatchlistRenameBtn');
    var watchlistDeleteBtn = document.getElementById('mccWatchlistDeleteBtn');

    if (watchlistSelect) {
      watchlistSelect.addEventListener('change', function () {
        state.activeWatchlistId = toPosInt(watchlistSelect.value, activeWatchlistId());
        renderWatchlistSelectors();
        state.briefing = [];
        renderBriefing();
        loadWatchlistItems({ reset: true }).catch(handleApiError);
      });
    }

    function triggerWatchlistSearch(immediate) {
      if (!watchlistSearchInput) return;
      var nextQuery = String(watchlistSearchInput.value || '').trim();
      if (state.watchlistSearchTimer) {
        clearTimeout(state.watchlistSearchTimer);
        state.watchlistSearchTimer = null;
      }
      function runSearch() {
        loadWatchlistItems({ query: nextQuery, reset: true }).catch(handleApiError);
      }
      if (immediate) runSearch();
      else state.watchlistSearchTimer = setTimeout(runSearch, 250);
    }

    if (watchlistSearchInput) {
      watchlistSearchInput.addEventListener('input', function () { triggerWatchlistSearch(false); });
      watchlistSearchInput.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter') {
          ev.preventDefault();
          triggerWatchlistSearch(true);
        }
      });
    }
    if (watchlistSearchBtn) {
      watchlistSearchBtn.addEventListener('click', function () { triggerWatchlistSearch(true); });
    }
    if (watchlistMoreBtn) {
      watchlistMoreBtn.addEventListener('click', function () {
        if (!state.watchlistHasMore) return;
        loadWatchlistItems({ append: true }).catch(handleApiError);
      });
    }
    if (watchlistCreateBtn && watchlistNameInput) {
      watchlistCreateBtn.addEventListener('click', function () {
        createWatchlist(watchlistNameInput.value).catch(handleApiError);
      });
    }
    if (watchlistRenameBtn && watchlistNameInput) {
      watchlistRenameBtn.addEventListener('click', function () {
        renameActiveWatchlist(watchlistNameInput.value).catch(handleApiError);
      });
    }
    if (watchlistDeleteBtn) {
      watchlistDeleteBtn.addEventListener('click', function () {
        if (!window.confirm('Delete selected watchlist? Non-empty watchlists cannot be deleted.')) return;
        deleteActiveWatchlist().catch(handleApiError);
      });
    }

    setPane('overview');
    boot();
  });
})();
