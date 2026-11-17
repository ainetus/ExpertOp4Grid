# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Layer / section constants for the interactive HTML viewer."""

from typing import Dict, List

# Section names rendered as <h3> headers in the sidebar layer list.
# Layers carry their section in the model so the JS just groups by it.
_SECTION_STRUCTURAL = "Structural Paths"
_SECTION_PROPERTIES = "Individual entities properties"
_SECTION_FLOWS = "Flow redispatch values"

# Edge color → human-readable layer label. Restricted to the three flow
# polarities (positive / negative / null). The historical "black" /
# "gray" / "darkred" buckets are dropped because they are redundant
# with the explicit semantic flags (is_overload / is_monitored) or
# carry no operational meaning on their own.
_LAYER_LABELS: Dict[str, str] = {
    "coral": "Positive",
    "blue": "Negative",
    "dimgray": "Null",
}

# Edge style → layer label (orthogonal to color).
_STYLE_LAYERS: Dict[str, str] = {
    "dotted": "Non-reconnectable",
    "dashed": "Reconnectable",
    "tapered": "Swapped flow",
}

# Source-of-truth attribute layers — values produced upstream by
# alphaDeesp / expert_op4grid_recommender as explicit boolean flags on
# nodes and/or edges. The viewer scans for them and exposes a layer
# toggle for each. Defining them here (rather than guessing from edge
# colours / shapes) keeps the layer list semantically stable when the
# visual palette evolves.
#
# Each entry:
#   key            — `data-attr-*` flag scanned on node and edge groups
#   label          — human-readable sidebar label
#   swatch         — special-case identifier consumed by the JS
#                    template to render an inline SVG glyph (no colour
#                    chip — these layers cut across the colour palette)
#   scope          — "node", "edge", or "both"
_SEMANTIC_LAYERS: List[Dict[str, str]] = [
    {"key": "on_constrained_path", "label": "Constrained path", "swatch": "constrained-path", "scope": "both"},
    {"key": "in_red_loop", "label": "Red-loop paths", "swatch": "red-loop", "scope": "both"},
    # Evacuation antennas (stamped by expert_op4grid_recommender): parts of
    # the grid whose net production leaves through a single node of the
    # constrained path. Their report is insignificant, yet they are a lever;
    # the renderer keeps them in the reduced view.
    {"key": "in_evacuation_antenna", "label": "Evacuation antennas", "swatch": "evacuation-antenna", "scope": "both"},
    {"key": "is_overload", "label": "Overloads", "swatch": "overload", "scope": "edge"},
    {"key": "is_monitored", "label": "Low margin lines", "swatch": "monitored", "scope": "edge"},
    # Operator-supplied extras (ExpertAgent's `additionalLinesToCut`):
    # cut in the analysis like overloads but rendered with their
    # natural flow colour and excluded from the Overloads /
    # Low margin lines layers.  Surfaced as a dedicated layer so the
    # operator can still see how their choice materialised.
    {"key": "is_extra_cut", "label": "Extra lines to prevent flow increase", "swatch": "extra-cut", "scope": "edge"},
    {"key": "is_hub", "label": "Hubs", "swatch": "diamond", "scope": "node"},
]

# Threshold below which a node's ``value`` (prod − load, in MW) is
# treated as "no real prod/load here". Build-time conventions in the
# upstream simulators tag every node with ``prod_or_load="load"`` and
# ``value="0.0"`` even when no consumption exists, so a strict
# ``prod_or_load == "load"`` test would flood the layer with empty
# nodes. The 1 MW floor matches operator practice.
_PROD_LOAD_VALUE_FLOOR_MW = 1.0

# Per-kind config for the value-based node layers. Matched against the
# ``prod_or_load`` attribute set by ``build_nodes`` upstream
# (alphaDeesp/core/graphs/power_flow_graph.py and the simulator-specific
# build_nodes_v2 helpers). Each entry produces a single layer in the
# "Individual entities properties" section, populated only with the
# nodes whose absolute ``value`` clears ``_PROD_LOAD_VALUE_FLOOR_MW``.
_VALUE_NODE_LAYERS: List[Dict[str, str]] = [
    {"key": "prod", "label": "Production nodes", "swatch": "prod-node"},
    {"key": "load", "label": "Consumption nodes", "swatch": "load-node"},
]

# Per-layer-key section assignment. The JS renders one ``<h3>`` per
# section in the order the sections are first encountered.
_LAYER_SECTIONS: Dict[str, str] = {
    # Structural paths — multi-edge structures.
    "semantic:on_constrained_path": _SECTION_STRUCTURAL,
    "semantic:in_red_loop": _SECTION_STRUCTURAL,
    "semantic:in_evacuation_antenna": _SECTION_STRUCTURAL,
    # Individual entities properties — per-edge / per-node flags.
    "semantic:is_overload": _SECTION_PROPERTIES,
    "semantic:is_monitored": _SECTION_PROPERTIES,
    "semantic:is_extra_cut": _SECTION_PROPERTIES,
    "semantic:is_hub": _SECTION_PROPERTIES,
    "style:dashed": _SECTION_PROPERTIES,
    "style:dotted": _SECTION_PROPERTIES,
    "style:tapered": _SECTION_PROPERTIES,
    # Value-based node layers — see _VALUE_NODE_LAYERS / build_nodes.
    "node:prod": _SECTION_PROPERTIES,
    "node:load": _SECTION_PROPERTIES,
    # Flow polarity buckets.
    "color:coral": _SECTION_FLOWS,
    "color:blue": _SECTION_FLOWS,
    "color:dimgray": _SECTION_FLOWS,
}

# Render order: sections appear top-to-bottom in this order; layers
# within a section appear in the order the model emits them.
_SECTION_ORDER: List[str] = [
    _SECTION_STRUCTURAL,
    _SECTION_PROPERTIES,
    _SECTION_FLOWS,
]
