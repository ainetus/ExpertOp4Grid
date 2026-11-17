************
Architecture
************

This page is a developer-oriented map of ``alphaDeesp`` (the package behind
**ExpertOp4Grid**). It explains how the pieces fit together, the contracts
between them, and where to plug in new behaviour. For the algorithm's
*conceptual* description see :doc:`DESCRIPTION`; for a call-level walkthrough
see :doc:`DETAILS`.

Pipeline overview
=================

Given an overloaded line, the system builds an *influence graph* around the
overload, ranks candidate substations/topologies, simulates the top-ranked
ones and returns a score (0–4) per remediation::

    config.ini + CLI ─► alphaDeesp.main
                              │ builds
                              ▼
        Grid2opSimulation / PypownetSimulation      (subclass of core.simulation.Simulation)
                              │ topology, dataframe, mappings
                              ▼
                  expert_operator.expert_operator()
                              │
                              ├─► OverFlowGraph            (core/graphs/overflow_graph.py)
                              ├─► Structured_Overload_Distribution_Graph
                              ├─► AlphaDeesp.get_ranked_combinations()
                              └─► sim.compute_new_network_changes() ─► end-result DataFrame

The orchestration lives in :func:`alphaDeesp.expert_operator.expert_operator`.
Everything upstream of it is a *backend adapter*; everything downstream is the
backend-agnostic expert system.

The Simulation contract (backend port)
======================================

:class:`alphaDeesp.core.simulation.Simulation` is an abstract base class — the
single seam a new grid backend must implement. Concrete backends
(``Grid2opSimulation``, the deprecated ``PypownetSimulation``) subclass it and
provide the topology, the flow DataFrame and the id mappings the expert system
needs.

Key abstract methods a backend must supply:

``get_dataframe()``
    One row per line with at least ``idx_or``, ``idx_ex``, ``init_flows``,
    ``new_flows``, ``delta_flows``, ``swapped`` and ``gray_edges``. Built by the
    base ``create_df`` helper, which the backend feeds via
    ``cut_lines_and_recomputes_flows``.
``get_substation_elements()``
    ``{substation_id: [element, ...]}`` where each element is a
    :class:`~alphaDeesp.core.elements.Production`,
    :class:`~alphaDeesp.core.elements.Consumption`,
    :class:`~alphaDeesp.core.elements.OriginLine` or
    :class:`~alphaDeesp.core.elements.ExtremityLine`.
``isAntenna`` / ``isDoubleLine`` / ``getLinesAtSubAndBusbar``
    Topology predicates used to prune candidate actions.
``compute_new_network_changes(ranked_combinations)``
    Simulate the recommended topologies and return the end-result DataFrame.

**Row-per-line invariant.** The DataFrame is one row per line, in line-id
order. The overloaded line's redispatch is read *positionally* by line id, and
``OverFlowGraph`` matches ``lines_to_cut`` against row positions — keep that
ordering when producing the frame.

The ``graphs`` package
======================

``core/graphsAndPaths.py`` is a **backwards-compatible shim** re-exporting the
public surface of the ``core/graphs/`` package. External code can keep importing
``from alphaDeesp.core.graphsAndPaths import OverFlowGraph, ...``; new code should
import from ``alphaDeesp.core.graphs``. The public surface is pinned by
``tests/test_graphs_package.py`` (``EXPECTED_PUBLIC_NAMES`` /
``EXPECTED_SUBMODULES``).

Semantic model vs. renderer
---------------------------

``OverFlowGraph`` is split into a **semantic model** and a **renderer**:

* :class:`~alphaDeesp.core.graphs.overflow_graph.OverFlowGraph` owns the model —
  the ``MultiDiGraph`` topology, per-edge redispatch magnitude, the edge *role*
  encoded as a base colour, and the boolean semantic flags consumed downstream
  (``is_overload``, ``is_monitored``, ``on_constrained_path``, ``in_red_loop``,
  ``is_hub``, ``is_extra_cut``). Callers may also stamp
  ``in_evacuation_antenna`` on the evacuation antennas they detect.
* :class:`~alphaDeesp.core.graphs.overflow_renderer.OverflowGraphRenderer` owns
  all Graphviz *presentation* — penwidth scaling, node shapes, tapered swap
  styling, the compound ``"colour:yellow:colour"`` highlight strings, HTML
  loading labels, the drawing of evacuation antennas (kept in the reduced view,
  in ochre), and plotting. It is **stateless** (static methods over a
  passed-in graph), so downstream repositories can reuse it on any compatible
  ``MultiDiGraph``.

Semantic edge roles
-------------------

Never parse a Graphviz colour string. The base colour of an edge encodes a
stable *role*:

===============  ==========================================  =====================================
base colour      role (``edge_roles``)                       meaning
===============  ==========================================  =====================================
``black``        ``EDGE_ROLE_OVERLOAD``                       overloaded contingency line
``blue``         ``EDGE_ROLE_NEGATIVE``                       negative redispatch (into the overload)
``coral``        ``EDGE_ROLE_POSITIVE``                       positive redispatch (loop / away)
``gray``         ``EDGE_ROLE_INSIGNIFICANT``                  below-threshold redispatch
``dimgray``      ``EDGE_ROLE_NULL_NON_RECONNECTABLE``         null-flow, non-reconnectable line
===============  ==========================================  =====================================

:func:`~alphaDeesp.core.graphs.edge_roles.edge_role_of` is the single authority
mapping an edge's base colour to its role. It prefers the stable ``base_color``
attribute (recorded by the renderer when it wraps a colour into a compound
highlight) and is compound-safe. ``OverFlowGraph.edge_role(name)`` is the
convenience by-line-name accessor.

Structured overload graph
-------------------------

:class:`~alphaDeesp.core.graphs.structured_overload_graph.Structured_Overload_Distribution_Graph`
turns a coloured overflow graph into the path structure the ranking needs:

* **constrained path** — the black (overload) + blue (negative) network that
  funnels current into the overloads (see
  :class:`~alphaDeesp.core.graphs.constrained_path.ConstrainedPath`);
* **red loops** — parallel coral paths onto which flow can be rerouted;
* **hubs** — substations where a loop path meets the constrained path.

Its colour-filtered views, ``red_loops`` and ``hubs`` are lazy
``functools.cached_property`` computed from a **construction-time snapshot** of
the graph (so a later mutation of the caller's graph does not leak into the
views). ``red_loops`` uses the constructor *seed* hubs; the public
``find_loops()`` re-enumerates with the *detected* hubs — this split keeps the
lazy properties order-independent while matching the historical eager
behaviour.

Null-flow and consolidation
---------------------------

Two mixins fold onto ``OverFlowGraph``:

* :class:`~alphaDeesp.core.graphs.null_flow_graph.NullFlowGraphMixin` — decides
  which disconnected/reconnectable "null-flow" lines lie on short paths bridging
  the constrained/dispatch sides, via a per-component Dijkstra search. The
  routing weight is precomputed as an edge attribute (fast string weight);
  ``capacity_weighted=False`` (default) reproduces the historical hop-only
  behaviour bit-identically, ``True`` enables capacity-weighted routing.
* :class:`~alphaDeesp.core.graphs.graph_consolidation.GraphConsolidationMixin` —
  disambiguates the raw graph (recolouring / reversing edges) so the structured
  analysis is stable.

AlphaDeesp (ranking)
====================

:class:`alphaDeesp.core.alphadeesp.AlphaDeesp` scores candidate busbar splits.
Construction runs the pipeline by default::

    AlphaDeesp(graph, df, simulator_data, substation_in_cooldown)         # auto_run=True
    AlphaDeesp(graph, df, simulator_data, auto_run=False).run()           # staged / testable

The scoring helpers live in :class:`~alphaDeesp.core.topology_scorer.TopologyScorerMixin`
and the graph-mutation helpers (applying a busbar split, twin-node encoding) in
:class:`~alphaDeesp.core.topo_applicator.TopoApplicatorMixin`.
``AlphaDeesp_warmStart`` is the pre-existing "skip the pipeline" path (a caller
supplies a pre-built distribution graph).

Interactive HTML viewer
=======================

``core/interactive_html/`` builds a self-contained interactive viewer around a
Graphviz-rendered SVG (pan/zoom, hover, click-to-highlight, search, semantic
layer toggles). It is a package: the CSS/JS/HTML skeleton are externalised under
``assets/`` and reassembled at runtime by ``template.html_template()`` — edit the
``.css`` / ``.js`` assets directly. The viewer reads the semantic flags
(``is_overload`` …) rather than reinterpreting colours, which is why those flags
are the source of truth on the model.

Extending the system
=====================

* **New grid backend** — subclass :class:`~alphaDeesp.core.simulation.Simulation`
  and implement its abstract methods; nothing else in the pipeline needs to
  change.
* **New rendering** — reuse or subclass
  :class:`~alphaDeesp.core.graphs.overflow_renderer.OverflowGraphRenderer`; it is
  independent of the model.
* **New semantic layer** — stamp a boolean flag on the model
  (``OverFlowGraph``) and add it to the viewer's layer configuration; do not key
  new behaviour off colour strings.
