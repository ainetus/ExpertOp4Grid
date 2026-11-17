# Changelog

## [0.3.4] - 2026-11-17

Evacuation antennas in the overflow graph drawing (PR #80). The reduced view
keeps them, drawn in ochre with their report, and the interactive viewer offers
them as a layer. This is rendering only: the analysis outputs are unchanged, and
callers that never stamp `in_evacuation_antenna` get the same drawing as with
0.3.3. 460 runnable tests (CI command) pass.

### Added

- **Evacuation antennas in the overflow graph drawing.** An evacuation antenna
  is a part of the grid whose net production leaves through a single node of
  the constrained path (or several, when insensitive). Its report is
  insignificant, so its edges are gray, yet it is a lever.
  expert_op4grid_recommender detects these antennas and stamps
  `in_evacuation_antenna` on their nodes and branches.
  - `OverflowGraphRenderer.prepare_for_plot` builds the graph actually drawn.
    The reduced view (`without_gray_edges`) keeps the flagged gray edges and
    the antenna nodes, with their injection colours like every other node.
    The edges are drawn in an ochre yellow, `EVACUATION_ANTENNA_COLOR`
    (`darkgoldenrod`), and keep the same conventions as the other edges:
    report label and arrow.
  - Everything happens on a copy: the model's colours are analysis data
    (`Structured_Overload_Distribution_Graph` builds its views from them), so
    they are never repainted. A drawn antenna edge keeps `base_color="gray"`,
    and an antenna edge with a significant report keeps its colour.
  - `delete_color_edges` gains `keep_flags`, which spares the edges carrying
    one of the given boolean flags. The analysis views do not pass it.
  - The interactive viewer gains an **Evacuation antennas** layer in the
    *Structural Paths* section, with a dedicated glyph. A test now checks that
    every semantic layer's swatch has a glyph in `viewer.js`, and
    `docs/ARCHITECTURE.rst` lists that glyph among the steps to add a layer.
  - `OverflowGraphRenderer.plot` draws the prepared graph, with the layout of
    exactly the nodes it keeps (tested with a fake printer).

  On a full-France snapshot (contingency `MERLAL62SOULL`), the reduced view
  goes from 26 to 33 nodes: the 7 substations and 14 branches of the Vent des
  Îles offshore park antenna (231 MW) were dropped before and are now drawn.

## [0.3.3] - 2026-07-16

Large architecture-review pass over the `alphaDeesp` graph layer: correctness
fixes, performance work, two deep revisions, the interactive-viewer
decomposition, and the fix for the multigraph Dijkstra-weight bug (issue #1).
All changes are unit-tested (372 runnable tests without grid2op) and checked by
adversarial multi-agent verification. Public import paths are unchanged.

### Bug Fixes

- **Multigraph Dijkstra weight in the null-flow path search** (issue #1): on the
  overflow `MultiDiGraph`, networkx passes a callable weight the `{key: attr}`
  parallel-edge view, so `_compute_sssp_paths`'s `attr.get("capacity", 0)`
  silently read `0` and routing was hop-cost-only. The routing weight is now
  precomputed as an edge attribute (string-weight Dijkstra) with a
  `capacity_weighted` switch: `False` (default) reproduces the historical
  behaviour **bit-identical** ("bless"); `True` enables capacity-weighted routing
  with correct min-parallel capacity and `(u,v)`/`(u,v,key)` promoted matching
  ("fix"). Threaded through `add_relevant_null_flow_lines[_all_paths]` so
  downstream callers can opt in without patching.
- **`shortest_paths.py`**: removed a dead branch and made the promoted-edge
  matching multigraph-correct (was silently weighting every parallel edge as `0`).
- **`OverFlowGraph.__init__` no longer mutates the caller's DataFrame** (copies
  it); `rename_nodes` loop variable clarified (behaviour unchanged).
- **`Structured_Overload_Distribution_Graph.get_dispatch_edges_nodes`** guards
  the empty-loops case (`red_loops.Path.sum()` no longer raises `TypeError` on a
  grid with no loop paths).
- **`to_DiGraph`** defaults a missing edge `capacity` to `0.0` (was `1.0`), which
  no longer skews `rank_red_loops`' min-cut.

### New Features / Deep revisions

- **`OverFlowGraph` model/renderer split**: new
  `graphs/overflow_renderer.py::OverflowGraphRenderer` owns all Graphviz
  presentation (penwidth, shapes, tapered styling, compound highlight colours,
  plotting); `OverFlowGraph` keeps the semantic model. New
  `graphs/edge_roles.py::edge_role_of` (+ `EDGE_ROLE_*`, `OverFlowGraph.edge_role`)
  is the single authority mapping an edge's base colour to a semantic role, so no
  consumer parses Graphviz colour strings; `highlight_significant_line_loading`
  records an authoritative `base_color`.
- **`AlphaDeesp` explicit pipeline**: the ranking pipeline moved to `run()`;
  `AlphaDeesp(..., auto_run=True)` (default) preserves the previous behaviour,
  `auto_run=False` builds the object without side effects.
- **Lazy `Structured_Overload_Distribution_Graph`**: colour-filtered views,
  `red_loops` and `hubs` are `functools.cached_property` computed from a
  construction-time snapshot — behaviour-identical and order-independent.

### Performance

- `delete_color_edges` accepts a colour **or an iterable of colours**, removing
  them in a single graph copy; the structured graph builds its derived views in
  single passes.
- `sort_hubs` and the initial-inflow lookup in `AlphaDeesp` are vectorised
  (were per-hub / per-edge `iterrows` scans).
- `simulation.create_df` is vectorised (was several `iterrows` passes;
  400-case differential fuzz pins equivalence).
- Null-flow Dijkstra uses a precomputed string weight instead of a per-edge
  Python callable.

### Maintainability

- `core/interactive_html.py` (976 LOC) split into the `core/interactive_html/`
  package (8 focused modules) with the CSS/JS/HTML skeleton externalised under
  `assets/` and reassembled byte-exactly at runtime (`package_data` shipped).
- `find_loops` / consolidation path enumeration gained opt-in cutoffs
  (`loop_path_cutoff`, default `None` = unbounded = original behaviour).
- New `docs/CODE_REVIEW.md` (full review + downstream-impact analysis on
  `Expert_op4grid_recommender` + remaining-work backlog); `CLAUDE.md` refreshed.

### Tests

- New suites: `test_edge_roles.py`, `test_overflow_renderer.py`,
  `test_simulation_create_df.py`, `test_null_flow_weighting.py`; expanded
  `test_graphs_package.py`, `test_overflow_graph.py`, `test_alphadeesp_unit.py`,
  `test_shortest_paths.py`, `test_interactive_html.py`.

## [0.3.2.post4] - 2026-06-17

### New Features

- **Readable node names in the interactive overflow viewer** (PR #78): the
  viewer now uses each node's human-readable display label (e.g. a
  voltage-level name such as `Saucats 400kV`, set via the Graphviz `label`
  node attribute by the upstream recommender) instead of only the raw node
  id. Search matches on **both** the readable display name and the stable id;
  the hover tooltip and selection panel show the readable name as the header
  with the id underneath only when it differs. Node identity (SVG `<title>` /
  `data-name`) is unchanged, so selection, adjacency highlight and
  double-click SLD resolution keep using the stable id.

### Bug Fixes

- **Do not leak the Graphviz `\N` placeholder**: label-less nodes carry the
  Graphviz `\N` ("use node name") placeholder in their label attribute;
  `nodeDisplayName` now ignores any backslash escape and falls back to the
  id, so tooltips/search never surface a literal `\N`.

### Tests

- `test_interactive_html.py`: readable label surfaces as `data-attr-label`
  without losing the id; search consults both id and resolved display name;
  tooltip/selection skip the duplicated `label` attribute; label-less nodes
  fall back to the id (no `\N` leak).

## [0.3.2.post2] - 2026-05-07

### New Features

- **Operator-supplied "extra lines to cut"** (PR #76): `OverFlowGraph` accepts an `extra_lines_to_cut` argument naming a subset of `lines_to_cut` that the operator chose to disconnect to prevent flow increase elsewhere (ExpertAgent's `additionalLinesToCut` semantic). Those edges keep their natural flow colour (coral/blue) instead of black/yellow, are stamped `is_extra_cut=True` (alongside `constrained=True`) so downstream consumers can find them by flag, and are excluded from `is_overload` / `is_monitored` tagging in `highlight_significant_line_loading`. The before% → after% loading annotation still fires on extras so the operator sees how their cut materialises.
- **Interactive HTML viewer layer**: new "Extra lines to prevent flow increase" semantic layer (`semantic:is_extra_cut`) with a dashed-blue swatch, surfaced under the "Individual entities properties" section.

### Tests

- `TestExtraLinesToCut` in `test_overflow_graph.py` covers default empty extras, set storage, natural coral/blue colour, `is_extra_cut`/`constrained` flagging, exclusion from overload/monitored layers while still annotating the label, and the legacy "no extras" path.
- `test_layer_index_emits_extra_cut_layer_with_endpoints` verifies the new viewer layer (endpoint nodes, swatch, label, section).
 
## [0.3.0.post1] - 2026-03-10
 
### New Features
 
- **Standardized overflow graph arrow sizes** (PR #66): Implemented linear scaling for `penwidth` in `OverFlowGraph` based on absolute delta flow. This ensures arrow sizes are reasonable and readable even for very high delta flows, with a standardized maximum penwidth.
- **Improved arrow scaling in PowerFlowGraph**: Also applied linear scaling to `PowerFlowGraph` for consistent visualization across different graph types.
 
### Bug Fixes
 
- **Fixed `collapse_red_loops` logic**: Optimized the node collapse condition to ensure ALL connected edges are coral before collapsing a node into a "point" shape.
 
### Tests
 
- Added unit tests for arrow scaling and `collapse_red_loops` in `test_graphs_and_paths_unit.py`.
- Adapted `test_visualization_filtering.py` in the recommender repo to verify `collapse_red_loops` call.
 

## [0.3.0] - 2026-02-10

### New Features

- **Filter graph components without overloads** (PR #64): Added `keep_overloads_components()` method to `OverFlowGraph` that filters out connected components not containing any overloaded (black) edges by recolouring them to grey. This ensures only components with actual overloads are considered significant in further analysis.

- **Collapse coral-only loop nodes** (PR #65): Added `collapse_red_loops()` method to `OverFlowGraph` that collapses nodes purely part of coral-only loops into "point" shapes for cleaner visualization. A node is collapsed when all its edges are coral, its shape is "oval", it has no peripheries attribute, and none of its edges are dashed or dotted.

### Performance Improvements

- **Optimized null flow detection** (PR #63): Major refactoring and performance optimization of the null flow line detection pipeline:
  - Extracted `_setup_null_flow_styles()` to avoid redundant style setup across target path iterations
  - Pre-compute structural info (red loop nodes, constrained path endpoints) once and reuse across all target paths
  - Replace `delete_color_edges` graph copy operations with direct edge color computation for connex analysis
  - Build gray component graph in a single edge pass instead of 3 sequential copy+remove operations
  - Use single-source Dijkstra per source node instead of per source-target pair, reducing from O(S*T) to O(S) Dijkstra calls
  - Pre-filter edges of interest to component membership for early exits
  - Cache BFS results and incident edge lookups to eliminate redundant computation
  - Flip negative capacities once globally instead of per source-target pair
  - Optimized `remove_unused_added_double_edge` to avoid subgraph creation
  - Optimized `add_double_edges_null_redispatch` from 4 `nx.get_edge_attributes` calls to a single edge pass
  - Increased `max_null_flow_path_length` default from 5 to 7
  - Properly handle double edges when finding relevant null flow paths

### Tests

- Added 78 unit tests for `graphsAndPaths` helper functions and `detect_edges_to_keep` (PR #63), covering: `delete_color_edges`, `nodepath_to_edgepath`, `incident_edges`, `from_edges_get_nodes`, `find_multidigraph_edges_by_name`, `shortest_path_with_promoted_edges`, `all_simple_edge_paths_multi`, `add_double_edges_null_redispatch`, `remove_unused_added_double_edge`, `detect_edges_to_keep`, `ConstrainedPath` methods, and `shortest_path_min_weight_then_hops`
- Added 13 unit tests for `keep_overloads_components` (PR #64), covering: component with/without overloads, multiple mixed components, already-gray edges, empty graph, single edges, parallel edges, gray bridge not merging components, three components, and idempotency

## [0.2.8]

### Performance Improvements

- Speed up path findings with smarter graph algorithms and rustworkx (PR #61)
- Speed up AlphaDeesp representation creation: optimize `create_and_fill_internal_structures`, accelerate `get_model_obj_from_or` and `get_model_obj_from_ext` (PR #62)
- Added `rustworkx` as a dependency for faster graph operations

### Features

- Added ability to consider undirected edges in loop paths (PR #59)
- Extended topology scoring to reduced specified action space with warm-start support (PR #58)
- Exposed depth and breadth search parameters for reconnectable lines in upper functions

## [0.2.7]

- Highlight non-connected paths with additional blue edge path info (PR #57)
- Ambiguous path handling improvements (PR #55, #56)
- Highlight possible overloads (PR #53, #54)
- Display reconnectable lines (PR #52)
- Improved graphviz constrained path visualization (PR #51)
- Getting started guide and examples (PR #50)
- Refactored plotting (PR #47, #48)
