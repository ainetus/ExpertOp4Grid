"""Unit tests for :class:`OverflowGraphRenderer`.

The renderer holds all Graphviz *presentation* logic extracted from
``OverFlowGraph``. These tests exercise it standalone (on bare graphs) to
prove the model/renderer split leaves the rendering reusable in isolation —
the reason downstream repositories can depend on it directly.
"""

import networkx as nx
import pandas as pd

from alphaDeesp.core.graphs.edge_roles import EDGE_ROLE_INSIGNIFICANT, edge_role_of
from alphaDeesp.core.graphs.overflow_renderer import (
    EVACUATION_ANTENNA_COLOR,
    OverflowGraphRenderer,
)
# The renderer must also be reachable through both public surfaces.
from alphaDeesp.core.graphs import OverflowGraphRenderer as _FromPackage
from alphaDeesp.core.graphsAndPaths import OverflowGraphRenderer as _FromShim


class TestPublicSurface:
    def test_exported_from_package_and_shim(self):
        assert _FromPackage is OverflowGraphRenderer
        assert _FromShim is OverflowGraphRenderer


class TestPenwidthScaling:
    def test_scaling_factor_and_visibility_floor(self):
        scaling, min_pen = OverflowGraphRenderer.penwidth_scaling(
            pd.Series([1000.0, 100.0, 10.0]))
        assert scaling == 15.0 / 1000.0
        # floor = max(1 MW * 0.015, 10% * 15) = max(0.015, 1.5) = 1.5
        assert abs(min_pen - 1.5) < 1e-9

    def test_all_zero_flow_falls_back_to_unit_scale(self):
        scaling, min_pen = OverflowGraphRenderer.penwidth_scaling(pd.Series([0.0]))
        assert scaling == 1.0
        assert min_pen == 1.5

    def test_edge_penwidth_is_clamped_to_floor(self):
        # tiny flow (10 MW) at the 1000-MW scale -> 0.15 raw, clamped to 1.5
        pen = OverflowGraphRenderer.edge_penwidth(
            10.0, scaling_factor=0.015, min_penwidth=1.5, float_precision="%.2f")
        assert pen == 1.5

    def test_edge_penwidth_scales_when_above_floor(self):
        pen = OverflowGraphRenderer.edge_penwidth(
            1000.0, scaling_factor=0.015, min_penwidth=1.5, float_precision="%.2f")
        assert pen == 15.0


class TestNodeShapes:
    def test_set_hub_shapes_only_marks_hubs(self):
        g = nx.MultiDiGraph()
        g.add_node("A")
        g.add_node("B")
        OverflowGraphRenderer.set_hub_shapes(g, ["A"], shape_hub="diamond")
        assert g.nodes["A"]["shape"] == "diamond"
        assert g.nodes["B"]["shape"] == "oval"

    def test_collapse_red_loops_collapses_pure_coral_oval(self):
        g = nx.MultiDiGraph()
        g.add_node("N1", shape="oval")
        g.add_edge("N1", "N2", color="coral")
        OverflowGraphRenderer.collapse_red_loops(g)
        assert g.nodes["N1"]["shape"] == "point"

    def test_collapse_red_loops_leaves_mixed_node_alone(self):
        g = nx.MultiDiGraph()
        g.add_node("N1", shape="oval")
        g.add_edge("N1", "N2", color="coral")
        g.add_edge("N1", "N3", color="blue")
        OverflowGraphRenderer.collapse_red_loops(g)
        assert g.nodes["N1"]["shape"] == "oval"


class TestSwappedFlowStyling:
    def test_swapped_lines_get_tapered_style(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="L1", color="coral")
        g.add_edge("B", "C", name="L2", color="blue")
        OverflowGraphRenderer.highlight_swapped_flows(g, ["L1"])
        l1 = g.edges[("A", "B", 0)]
        l2 = g.edges[("B", "C", 0)]
        assert l1["style"] == "tapered" and l1["dir"] == "both" and l1["arrowtail"] == "none"
        assert "style" not in l2


class TestHighlightFormatting:
    def test_compound_highlight_color(self):
        assert OverflowGraphRenderer.highlight_color("black") == '"black:yellow:black"'
        assert OverflowGraphRenderer.highlight_color("coral") == '"coral:yellow:coral"'

    def test_overload_label_emphasises_before(self):
        label = OverflowGraphRenderer.overload_label("x", 110, 80)
        assert "<B>110%</B>" in label and "80%" in label

    def test_low_margin_label_emphasises_after(self):
        label = OverflowGraphRenderer.low_margin_label("x", 90, 0)
        assert "90% → <B>0%</B>" in label


def _graph_with_antenna() -> nx.MultiDiGraph:
    """A --black--> B --blue--> C, an evacuation antenna P2 - P1 hanging off
    B (gray, flagged), and an insignificant edge C - D."""
    g = nx.MultiDiGraph()
    g.add_edge("A", "B", color="black", label="-80", name="overload")
    g.add_edge("B", "C", color="blue", label="-40", name="path")
    g.add_edge("P1", "B", color="gray", label="0", name="antenna_link",
               in_evacuation_antenna=True)
    g.add_edge("P2", "P1", color="gray", label="-0", name="antenna_inner",
               in_evacuation_antenna=True)
    g.add_edge("C", "D", color="gray", label="0", name="insignificant")
    return g


class TestEvacuationAntennas:
    def test_reduced_view_keeps_the_antenna_and_drops_other_gray_edges(self):
        drawn = OverflowGraphRenderer.prepare_for_plot(
            _graph_with_antenna(), without_gray_edges=True)
        names = {name for _, _, name in drawn.edges(data="name")}
        assert names == {"overload", "path", "antenna_link", "antenna_inner"}
        assert {"P1", "P2"} <= set(drawn.nodes)
        assert "D" not in drawn.nodes

    def test_antenna_edges_are_drawn_in_their_colour_with_their_report(self):
        drawn = OverflowGraphRenderer.prepare_for_plot(
            _graph_with_antenna(), without_gray_edges=True)
        link = drawn.edges[("P1", "B", 0)]
        inner = drawn.edges[("P2", "P1", 0)]
        assert link["color"] == inner["color"] == EVACUATION_ANTENNA_COLOR
        assert link["base_color"] == "gray"  # still an insignificant report
        assert edge_role_of(link) == EDGE_ROLE_INSIGNIFICANT
        # Same conventions as every other edge: report label, arrow.
        assert (link["label"], inner["label"]) == ("0", "-0")
        assert "dir" not in link

    def test_an_antenna_edge_with_a_significant_report_keeps_its_colour(self):
        g = _graph_with_antenna()
        g.add_edge("P1", "B", color="coral", label="12", name="antenna_sensitive",
                   in_evacuation_antenna=True)
        drawn = OverflowGraphRenderer.prepare_for_plot(g, without_gray_edges=True)
        assert drawn.edges[("P1", "B", 1)]["color"] == "coral"

    def test_full_view_styles_the_antenna_on_a_copy(self):
        g = _graph_with_antenna()
        drawn = OverflowGraphRenderer.prepare_for_plot(g)
        assert drawn is not g
        assert drawn.edges[("P1", "B", 0)]["color"] == EVACUATION_ANTENNA_COLOR
        assert drawn.edges[("C", "D", 0)]["color"] == "gray"

    def test_full_view_without_antenna_draws_the_graph_itself(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", color="gray", label="0", name="insignificant")
        assert OverflowGraphRenderer.prepare_for_plot(g) is g

    def test_the_model_graph_is_left_untouched(self):
        g = _graph_with_antenna()
        before = {edge: dict(data) for edge, data in g.edges.items()}
        for without_gray_edges in (True, False):
            OverflowGraphRenderer.prepare_for_plot(g, without_gray_edges)
        assert {edge: dict(data) for edge, data in g.edges.items()} == before
