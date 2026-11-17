"""OverflowGraphRenderer: Graphviz presentation for the overflow model.

This module isolates every *Graphviz-specific rendering* concern that used
to live inside :class:`~alphaDeesp.core.graphs.overflow_graph.OverFlowGraph`:

* penwidth scaling (edge thickness proportional to redispatch magnitude),
* node shapes (hub markers, collapsing pure-loop nodes to points),
* tapered styling for flow-direction swaps,
* the compound ``"colour:yellow:colour"`` highlight strings and the HTML
  ``before% → after%`` loading labels,
* the drawing of evacuation antennas (kept in the reduced view, in their own
  colour),
* the actual plotting via :class:`~alphaDeesp.core.printer.Printer`.

Keeping it separate draws a clean line between the **semantic model** —
edge *roles* encoded as base colours (black overload / blue negative / coral
positive / gray insignificant) plus boolean flags (``is_overload``,
``on_constrained_path`` …) owned by ``OverFlowGraph`` — and its **rendering**.
Downstream repositories that build their own semantic overflow graph can
reuse this renderer directly, and the model can be reasoned about (and
tested) without pulling in any Graphviz vocabulary.

All methods are **static** and operate on a passed-in graph, so the renderer
carries no state and can be applied to any compatible ``MultiDiGraph``.
"""

import logging
from math import fabs
from typing import Any, Dict, Iterable, List, Optional, Tuple

import networkx as nx

from alphaDeesp.core.printer import Printer
from alphaDeesp.core.graphs.graph_utils import delete_color_edges, is_flag_set

logger = logging.getLogger(__name__)

# Evacuation antennas: parts of the grid tied to the constrained path through
# a single node (or several, when insensitive), whose net production leaves
# through it. The caller stamps them (expert_op4grid_recommender's
# structural-antenna detection) with the ``in_evacuation_antenna`` flag. Their
# report is insignificant, so their edges are gray, yet they are a lever: the
# drawing keeps them, in an ochre yellow (see ``prepare_for_plot``).
EVACUATION_ANTENNA_FLAG = "in_evacuation_antenna"
EVACUATION_ANTENNA_COLOR = "darkgoldenrod"

# Penwidth thresholds used when stamping edge thickness.
# The floor is dynamic: at least the width equivalent to 1 MW of flow
# (``scaling_factor`` applied to 1.0), and at least 10 % of the largest
# rendered penwidth, so low / zero-flow edges (reconnectable,
# non-reconnectable, null-flow) remain visible without zooming.
_TARGET_MAX_PENWIDTH = 15.0
_MIN_PENWIDTH_FLOW_MW = 1.0
_MIN_PENWIDTH_FRACTION = 0.10


class OverflowGraphRenderer:
    """Stateless Graphviz renderer for overflow semantic graphs."""

    # ------------------------------------------------------------------
    # Penwidth (edge thickness)
    # ------------------------------------------------------------------

    @staticmethod
    def penwidth_scaling(delta_flows: Any) -> Tuple[float, float]:
        """Return ``(scaling_factor, min_penwidth)`` for a set of delta flows.

        ``scaling_factor`` maps the largest absolute flow onto
        ``_TARGET_MAX_PENWIDTH``; ``min_penwidth`` is the visibility floor.
        """
        max_abs_flow = abs(delta_flows).max() if len(delta_flows) else 0.0
        scaling_factor = (
            _TARGET_MAX_PENWIDTH / max_abs_flow if max_abs_flow > 0 else 1.0
        )
        min_penwidth = max(
            _MIN_PENWIDTH_FLOW_MW * scaling_factor,
            _MIN_PENWIDTH_FRACTION * _TARGET_MAX_PENWIDTH,
        )
        return scaling_factor, min_penwidth

    @staticmethod
    def edge_penwidth(
        reported_flow: float,
        scaling_factor: float,
        min_penwidth: float,
        float_precision: str,
    ) -> float:
        """Penwidth for a single edge, clamped to the visibility floor."""
        return max(
            float(float_precision % (fabs(reported_flow) * scaling_factor)),
            min_penwidth,
        )

    # ------------------------------------------------------------------
    # Node shapes
    # ------------------------------------------------------------------

    @staticmethod
    def set_hub_shapes(
        g: nx.MultiDiGraph, hubs: Iterable[Any], shape_hub: str = "circle"
    ) -> None:
        """Give every node an ``oval`` shape and hub nodes ``shape_hub``.

        This is the *visual* half of ``OverFlowGraph.set_hubs_shape``; the
        semantic ``is_hub`` / ``on_constrained_path`` / ``in_red_loop`` flags
        are stamped by the model.
        """
        dict_shapes = {node: "oval" for node in g.nodes}
        for hub in set(hubs):
            dict_shapes[hub] = shape_hub
        nx.set_node_attributes(g, dict_shapes, "shape")

    @staticmethod
    def collapse_red_loops(g: nx.MultiDiGraph) -> None:
        """Collapse purely-coral, non-hub oval nodes to ``point`` shapes.

        Purely a visual heuristic (point markers vs ovals); it sets no
        semantic attribute.
        """
        shapes = nx.get_node_attributes(g, "shape")
        peripheries = nx.get_node_attributes(g, "peripheries")
        edge_colors = nx.get_edge_attributes(g, "color")
        edge_styles = nx.get_edge_attributes(g, "style")

        nodes_to_collapse = {}
        for node in g.nodes:
            if shapes.get(node) != "oval":
                continue
            if node in peripheries and peripheries[node] >= 2:
                continue
            all_edges = list(g.in_edges(node, keys=True)) + list(g.out_edges(node, keys=True))
            if all_edges and OverflowGraphRenderer._all_edges_coral_no_dash(
                all_edges, edge_colors, edge_styles
            ):
                nodes_to_collapse[node] = "point"

        nx.set_node_attributes(g, nodes_to_collapse, "shape")

    @staticmethod
    def _all_edges_coral_no_dash(
        all_edges: List[Any],
        edge_colors: Dict[Any, str],
        edge_styles: Dict[Any, str],
    ) -> bool:
        """Return True when all edges are coral and none are dashed/dotted."""
        for edge in all_edges:
            if edge_colors.get(edge) != "coral":
                return False
            if edge_styles.get(edge, "") in ("dashed", "dotted"):
                return False
        return True

    # ------------------------------------------------------------------
    # Flow-direction swap styling
    # ------------------------------------------------------------------

    @staticmethod
    def highlight_swapped_flows(g: nx.MultiDiGraph, lines_swapped: List[Any]) -> None:
        """Draw lines whose flow direction has swapped in a tapered style."""
        edge_names = nx.get_edge_attributes(g, "name")
        swapped_edges = [edge for edge, name in edge_names.items() if name in lines_swapped]
        for attr_name, value in (("style", "tapered"), ("dir", "both"), ("arrowtail", "none")):
            nx.set_edge_attributes(g, {edge: value for edge in swapped_edges}, attr_name)

    # ------------------------------------------------------------------
    # Loading annotations (compound colour + HTML label)
    # ------------------------------------------------------------------

    @staticmethod
    def overload_label(current_x_label: Any, before: Any, after: Any) -> str:
        """HTML label for an overloaded edge (``before%`` emphasised)."""
        return f'< {current_x_label} <BR/>  <B>{before}%</B>  → {after}%>'

    @staticmethod
    def low_margin_label(current_x_label: Any, before: Any, after: Any) -> str:
        """HTML label for a low-margin / extra-cut edge (``after%`` emphasised)."""
        return f'< {current_x_label} <BR/>  {before}% → <B>{after}%</B> >'

    @staticmethod
    def highlight_color(current_edge_color: Any) -> str:
        """Compound Graphviz colour that yellow-tints an edge's base colour."""
        return f'"{current_edge_color}:yellow:{current_edge_color}"'

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    @staticmethod
    def prepare_for_plot(
        g: nx.MultiDiGraph, without_gray_edges: bool = False
    ) -> nx.MultiDiGraph:
        """Return the graph to draw: *g* itself, or a copy when the drawing
        differs from it. *g* is never modified.

        ``without_gray_edges`` drops the gray (insignificant) edges and the
        nodes they leave isolated, except the edges of evacuation antennas
        (``in_evacuation_antenna``). The gray edges of an antenna are drawn in
        ``EVACUATION_ANTENNA_COLOR``; like every other edge they keep their
        report label and arrow, and their ``base_color`` keeps the gray role.
        An antenna edge with a significant report keeps its colour.
        """
        antenna_edges = [
            (u, v, k)
            for u, v, k, data in g.edges(keys=True, data=True)
            if is_flag_set(data.get(EVACUATION_ANTENNA_FLAG)) and data.get("color") == "gray"
        ]
        if without_gray_edges:
            g = delete_color_edges(g, "gray", keep_flags=(EVACUATION_ANTENNA_FLAG,))
        elif antenna_edges:
            g = g.copy()
        for edge in antenna_edges:
            data = g.edges[edge]
            data.setdefault("base_color", data["color"])
            data["color"] = EVACUATION_ANTENNA_COLOR
        return g

    @staticmethod
    def plot(
        g: nx.MultiDiGraph,
        layout: Optional[List[Any]],
        rescale_factor: Optional[float] = None,
        allow_overlap: bool = True,
        fontsize: Optional[int] = None,
        node_thickness: int = 3,
        save_folder: str = "",
        without_gray_edges: bool = False,
    ) -> Any:
        """Render *g* with Graphviz, optionally dropping gray edges first
        (see :meth:`prepare_for_plot`)."""
        printer = Printer(save_folder)

        drawn = OverflowGraphRenderer.prepare_for_plot(g, without_gray_edges)
        if layout is not None and drawn.number_of_nodes() != g.number_of_nodes():
            layout_dict = {n: c for n, c in zip(g.nodes, layout)}
            layout = [layout_dict[node] for node in drawn.nodes]
        g = drawn

        kwargs = dict(rescale_factor=rescale_factor, fontsize=fontsize,
                      node_thickness=node_thickness, name="g_overflow_print")
        if save_folder == "":
            return printer.plot_graphviz(g, layout, allow_overlap=allow_overlap, **kwargs)
        printer.display_geo(g, layout, **kwargs)
        return None
