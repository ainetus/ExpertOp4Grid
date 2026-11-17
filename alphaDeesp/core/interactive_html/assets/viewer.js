
const MODEL = __MODEL_JSON__;
(function(){
  const svg = document.querySelector('#stage svg');
  const root = svg.querySelector('g.graph') || svg.querySelector('g');
  if (root && !root.classList.contains('graph')) root.classList.add('graph');

  // ---- Pan & zoom: native viewBox manipulation (~30 lines, no deps) ----
  let vb = (svg.getAttribute('viewBox') || '').split(/\s+/).map(Number);
  if (vb.length !== 4) { const r = svg.getBBox(); vb = [r.x, r.y, r.width, r.height]; }
  const initial = vb.slice();
  function setVB() { svg.setAttribute('viewBox', vb.join(' ')); }
  function clientToSvg(x, y) {
    const rect = svg.getBoundingClientRect();
    return { x: vb[0] + (x - rect.left) / rect.width * vb[2], y: vb[1] + (y - rect.top) / rect.height * vb[3] };
  }
  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const k = e.deltaY < 0 ? 0.85 : 1.18;
    const p = clientToSvg(e.clientX, e.clientY);
    vb[0] = p.x - (p.x - vb[0]) * k;
    vb[1] = p.y - (p.y - vb[1]) * k;
    vb[2] *= k; vb[3] *= k;
    setVB();
  }, { passive: false });
  let dragStart = null;
  svg.addEventListener('mousedown', (e) => { if (e.button !== 0) return; dragStart = { x: e.clientX, y: e.clientY, vb: vb.slice() }; svg.classList.add('dragging'); });
  window.addEventListener('mouseup', () => { dragStart = null; svg.classList.remove('dragging'); });
  window.addEventListener('mousemove', (e) => {
    if (!dragStart) return;
    const rect = svg.getBoundingClientRect();
    vb[0] = dragStart.vb[0] - (e.clientX - dragStart.x) / rect.width * vb[2];
    vb[1] = dragStart.vb[1] - (e.clientY - dragStart.y) / rect.height * vb[3];
    setVB();
  });
  document.getElementById('zoom-in').onclick = () => zoomBy(0.8);
  document.getElementById('zoom-out').onclick = () => zoomBy(1.25);
  document.getElementById('zoom-reset').onclick = () => { vb = initial.slice(); setVB(); };
  function zoomBy(k) {
    const cx = vb[0] + vb[2]/2, cy = vb[1] + vb[3]/2;
    vb[0] = cx - (cx - vb[0]) * k; vb[1] = cy - (cy - vb[1]) * k;
    vb[2] *= k; vb[3] *= k; setVB();
  }

  // ---- Adjacency lookup, hover, click-highlight ----
  const tooltip = document.getElementById('tooltip');
  const info = document.getElementById('info');
  function fmtAttrs(prefix, el, skip) {
    const out = [];
    const skipSet = skip ? new Set(skip) : null;
    for (const a of el.attributes) {
      if (a.name.startsWith('data-' + prefix + '-')) {
        const k = a.name.slice(('data-' + prefix + '-').length);
        if (skipSet && skipSet.has(k)) continue;
        out.push('<span class="key">' + k + '</span>: ' + a.value);
      }
    }
    return out.join('<br>');
  }
  // Display name for a node: the readable ``label`` (e.g. a voltage-level
  // name such as "Saucats 400kV") when present, else the stable node id
  // (``data-name``). The id is preserved as the node identity for
  // selection / adjacency / double-click resolution; ``label`` only
  // changes what the operator reads.
  function nodeDisplayName(el) {
    if (!el) return '';
    const label = el.getAttribute('data-attr-label');
    // Graphviz stores an *unset* label as the placeholder "\N" (meaning
    // "node name"); any backslash escape (\N, \G, …) is not a readable
    // name, so fall back to the stable id (data-name) in that case.
    if (label && label.indexOf('\\') === -1) return label;
    return el.getAttribute('data-name') || '';
  }
  // Tooltip / selection header for a node: readable name in bold, with the
  // raw id shown underneath only when it differs from the readable name.
  function nodeHeaderHtml(el) {
    const disp = nodeDisplayName(el);
    const id = el.getAttribute('data-name') || '';
    let head = '<b>' + escapeHtml(disp) + '</b>';
    if (id && id !== disp) head += '<br><span class="key">id</span>: ' + escapeHtml(id);
    return head;
  }
  function showTooltip(e, html) {
    tooltip.innerHTML = html;
    tooltip.style.display = 'block';
    const r = svg.getBoundingClientRect();
    tooltip.style.left = (e.clientX - r.left + 12) + 'px';
    tooltip.style.top = (e.clientY - r.top + 12) + 'px';
  }
  function hideTooltip() { tooltip.style.display = 'none'; }

  function clearSelection() {
    root.classList.remove('has-selection');
    root.querySelectorAll('.hl, .selected').forEach(el => el.classList.remove('hl', 'selected'));
    info.textContent = 'Nothing selected.';
  }
  function selectNode(name) {
    clearSelection();
    const node = root.querySelector('.node[data-name="' + cssEscape(name) + '"]');
    if (!node) return;
    root.classList.add('has-selection');
    node.classList.add('selected', 'hl');
    const neighbours = MODEL.adjacency[name] || [];
    for (const n of neighbours) {
      const nb = root.querySelector('.node[data-name="' + cssEscape(n.node) + '"]');
      if (nb) nb.classList.add('hl');
      const ed = document.getElementById(n.edge);
      if (ed) ed.classList.add('hl');
    }
    info.innerHTML = nodeHeaderHtml(node) + '<br>' + fmtAttrs('attr', node, ['label'])
      + '<br><br>degree: ' + neighbours.length;
  }
  function cssEscape(s) { return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/(["\\])/g, '\\$1'); }
  function escapeHtml(s) { return s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

  root.addEventListener('mouseover', (e) => {
    const g = e.target.closest('.node, .edge'); if (!g) return;
    if (g.classList.contains('node')) {
      showTooltip(e, nodeHeaderHtml(g) + '<br>' + fmtAttrs('attr', g, ['label']));
    } else {
      const lbl = g.querySelector('text'); const name = g.getAttribute('data-attr-name') || '';
      showTooltip(e, '<b>' + escapeHtml(g.getAttribute('data-source')) + ' → ' + escapeHtml(g.getAttribute('data-target')) + '</b>'
        + (name ? '<br>' + escapeHtml(name) : '')
        + '<br>' + fmtAttrs('attr', g));
    }
  });
  root.addEventListener('mousemove', (e) => {
    if (tooltip.style.display === 'block') {
      const r = svg.getBoundingClientRect();
      tooltip.style.left = (e.clientX - r.left + 12) + 'px';
      tooltip.style.top = (e.clientY - r.top + 12) + 'px';
    }
  });
  root.addEventListener('mouseout', hideTooltip);
  root.addEventListener('click', (e) => {
    const g = e.target.closest('.node'); if (!g) return;
    e.stopPropagation();
    selectNode(g.getAttribute('data-name'));
  });
  svg.addEventListener('click', (e) => { if (e.target === svg || e.target === root) clearSelection(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { clearSelection(); document.getElementById('search').value = ''; applySearch(); }});

  // ---- Search ----
  function applySearch() {
    const q = document.getElementById('search').value.trim().toLowerCase();
    root.querySelectorAll('.node.match').forEach(n => n.classList.remove('match'));
    if (!q) { root.classList.remove('has-search'); return; }
    root.classList.add('has-search');
    let count = 0;
    root.querySelectorAll('.node').forEach(n => {
      // Match against both the stable id (data-name) and the resolved
      // readable display name (e.g. a voltage-level name), so operators can
      // find a node by either spelling. nodeDisplayName ignores the
      // graphviz "\N" placeholder, so label-less nodes match on their id.
      const id = (n.getAttribute('data-name') || '').toLowerCase();
      const disp = nodeDisplayName(n).toLowerCase();
      if (id.indexOf(q) !== -1 || (disp && disp.indexOf(q) !== -1)) {
        n.classList.add('match'); count++;
      }
    });
  }
  document.getElementById('search').addEventListener('input', applySearch);

  // ---- Layer toggles ----
  // Membership-based dim model: every node and edge knows which
  // layers claim it. An element is **visible** iff at least one of
  // its claiming layers is currently checked. Elements with no
  // memberships at all are dimmed whenever any layer toggle differs
  // from the default "all checked" state — that matches the
  // user-facing intent that ticking a single layer focuses the view
  // on that layer only and recedes everything else.
  const layersEl = document.getElementById('layers');
  function swatchInner(swatch) {
    if (!swatch) return '<span style="display:block;width:100%;height:100%;border:1px dashed #999"></span>';
    const COLORED = {coral:1, blue:1, black:1, gray:1, dimgray:1, darkred:1, red:1, green:1};
    if (COLORED[swatch]) return '';
    if (swatch === 'diamond') return '<svg viewBox="0 0 10 10"><polygon points="5,0 10,5 5,10 0,5" fill="#444"/></svg>';
    if (swatch === 'red-loop') return '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="2" fill="coral"/><circle cx="5" cy="5" r="4" fill="none" stroke="coral" stroke-width="1"/></svg>';
    if (swatch === 'constrained-path') return '<svg viewBox="0 0 14 6"><line x1="0" y1="3" x2="14" y2="3" stroke="black" stroke-width="2"/></svg>';
    // Same colour as the renderer's EVACUATION_ANTENNA_COLOR.
    if (swatch === 'evacuation-antenna') return '<svg viewBox="0 0 14 6"><line x1="0" y1="3" x2="14" y2="3" stroke="darkgoldenrod" stroke-width="2"/></svg>';
    if (swatch === 'overload') return '<svg viewBox="0 0 14 6"><line x1="0" y1="3" x2="14" y2="3" stroke="black" stroke-width="2.5"/><line x1="0" y1="3" x2="14" y2="3" stroke="yellow" stroke-width="0.8"/></svg>';
    if (swatch === 'monitored') return '<svg viewBox="0 0 14 6"><line x1="0" y1="3" x2="14" y2="3" stroke="coral" stroke-width="2.5"/><line x1="0" y1="3" x2="14" y2="3" stroke="yellow" stroke-width="0.8"/></svg>';
    if (swatch === 'extra-cut') return '<svg viewBox="0 0 14 6"><line x1="0" y1="3" x2="14" y2="3" stroke="blue" stroke-width="2" stroke-dasharray="3 2"/></svg>';
    // Match the upstream node fillcolors set in build_nodes:
    //   prod (prod_minus_load > 0)  → coral
    //   load (prod_minus_load < 0)  → lightblue
    if (swatch === 'prod-node') return '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="coral" stroke="#444" stroke-width="0.6"/></svg>';
    if (swatch === 'load-node') return '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="lightblue" stroke="#444" stroke-width="0.6"/></svg>';
    return '';
  }
  function swatchStyle(swatch) {
    const COLORED = {coral:1, blue:1, black:1, gray:1, dimgray:1, darkred:1, red:1, green:1};
    if (COLORED[swatch]) return 'background:' + swatch;
    return 'background:#fff';
  }

  // Build per-element layer membership maps once. These are consulted
  // by `applyAllLayers()` on every checkbox change so an element
  // claimed by multiple layers never gets stuck in `layer-off`
  // because an unrelated checkbox flipped the wrong way.
  const nodeMemberships = new Map();  // data-name -> Array<layerIndex>
  const edgeMemberships = new Map();  // edge id  -> Array<layerIndex>
  for (let i = 0; i < MODEL.layers.length; i++) {
    const layer = MODEL.layers[i];
    for (const n of (layer.nodes || [])) {
      const arr = nodeMemberships.get(n);
      if (arr) arr.push(i); else nodeMemberships.set(n, [i]);
    }
    for (const e of (layer.edges || [])) {
      const arr = edgeMemberships.get(e);
      if (arr) arr.push(i); else edgeMemberships.set(e, [i]);
    }
  }

  const layerCheckboxes = [];
  let lastSection = null;
  for (const layer of MODEL.layers) {
    if (layer.section && layer.section !== lastSection) {
      const header = document.createElement('h3');
      header.className = 'layer-section-header';
      header.textContent = layer.section;
      layersEl.appendChild(header);
      lastSection = layer.section;
    }
    const id = 'layer-' + layer.key.replace(/[^a-z0-9]/gi, '-');
    const wrap = document.createElement('label');
    const total = (layer.nodes ? layer.nodes.length : 0) + (layer.edges ? layer.edges.length : 0);
    wrap.innerHTML = '<input type="checkbox" id="' + id + '" checked>'
      + '<span class="swatch" style="' + swatchStyle(layer.swatch) + '">' + swatchInner(layer.swatch) + '</span>'
      + '<span>' + escapeHtml(layer.label) + ' <span style="color:var(--muted)">(' + total + ')</span></span>';
    layersEl.appendChild(wrap);
    const cb = wrap.querySelector('input');
    layerCheckboxes.push(cb);
    cb.addEventListener('change', (e) => {
      applyAllLayers();
      window.parent.postMessage({
        type: 'cs4g:overflow-layer-toggled',
        key: layer.key,
        label: layer.label,
        visible: e.target.checked
      }, '*');
    });
  }

  function applyAllLayers() {
    const checkedSet = new Set();
    let allChecked = true;
    for (let i = 0; i < layerCheckboxes.length; i++) {
      if (layerCheckboxes[i].checked) checkedSet.add(i);
      else allChecked = false;
    }
    function shouldDim(memberships) {
      if (allChecked) return false;
      if (!memberships || memberships.length === 0) return true;
      for (const idx of memberships) {
        if (checkedSet.has(idx)) return false;
      }
      return true;
    }
    root.querySelectorAll('.node').forEach((el) => {
      const name = el.getAttribute('data-name');
      el.classList.toggle('layer-off', shouldDim(nodeMemberships.get(name)));
    });
    root.querySelectorAll('.edge').forEach((el) => {
      const id = el.getAttribute('id');
      el.classList.toggle('layer-off', shouldDim(edgeMemberships.get(id)));
    });
  }
  // Expose for testability and external triggers (e.g. parent app
  // requesting a full repaint after dynamic content updates).
  window.__cs4gApplyAllLayers = applyAllLayers;

  function setAllLayers(visible) {
    let changed = false;
    for (let i = 0; i < layerCheckboxes.length; i++) {
      if (layerCheckboxes[i].checked !== visible) {
        layerCheckboxes[i].checked = visible;
        changed = true;
      }
    }
    if (changed) applyAllLayers();
    window.parent.postMessage({
      type: 'cs4g:overflow-select-all-layers',
      visible: visible
    }, '*');
  }
  document.getElementById('layers-select-all').addEventListener('click', () => setAllLayers(true));
  document.getElementById('layers-select-none').addEventListener('click', () => setAllLayers(false));

  // Double-click on a graph node bubbles up to the parent window,
  // which is responsible for opening the corresponding Single-Line
  // Diagram view. The node `data-name` is the voltage-level (or
  // substation, depending on backend) identifier the parent will
  // resolve to a SLD endpoint.
  root.addEventListener('dblclick', (ev) => {
    const g = ev.target.closest('.node');
    if (!g) return;
    ev.preventDefault();
    ev.stopPropagation();
    const name = g.getAttribute('data-name') || '';
    if (!name) return;
    window.parent.postMessage({
      type: 'cs4g:overflow-node-double-clicked',
      name: name
    }, '*');
  });

  document.getElementById('stats').textContent =
    MODEL.nodes.length + ' nodes, ' + MODEL.edges.length + ' edges';
})();
