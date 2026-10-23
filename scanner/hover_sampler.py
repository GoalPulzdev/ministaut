"""Read-only visible-tooltip sampler driven by changes between hover positions.

Unlike V4 this does NOT require the tooltip to disappear off-map. Several
React/canvas seat maps leave the last tooltip visible while the pointer moves.
A candidate is accepted only if its section/capacity/free value becomes visible
AFTER a new hover coordinate and is stable across two consecutive reads.
A permanently visible old tooltip will never be counted as a new transition.
"""
from __future__ import annotations
from parser import Observation
from verification import parse_visible_texts


def _same(a: Observation, b: Observation) -> bool:
    return a.section == b.section and a.capacity == b.capacity and abs(a.free - b.free) <= 2


def _signature(h: Observation) -> tuple:
    return (h.section, h.free, h.capacity)


class HoverTransitionSampler:
    def __init__(self, page, text_reader, hover_ms: int = 80, diagnostics=None):
        self.page = page
        self.reader = text_reader
        self.ms = max(50, int(hover_ms))
        self.diagnostics = diagnostics if diagnostics is not None else {}
        self.diagnostics['sampler'] = 'v5-tooltip-transition'
        self.last_visible = {}
        self.initialized = False

    def _read(self, source, x, y):
        hits = parse_visible_texts(self.reader(self.page), source, x, y)
        # One popup per field; a page could momentarily contain multiple.
        return {h.section: h for h in hits}

    def initialize(self):
        vp = self.page.viewport_size or {'width': 1360, 'height': 740}
        self.page.mouse.move(vp['width'] - 24, vp['height'] - 24)
        self.page.wait_for_timeout(160)
        self.last_visible = self._read('initial-baseline', -1, -1)
        self.initialized = True
        self.diagnostics['initial_visible_popup_fields'] = sorted(self.last_visible)

    def hover(self, x, y, source):
        if not self.initialized:
            self.initialize()
        previous = self.last_visible
        self.page.mouse.move(x, y)
        self.page.wait_for_timeout(self.ms)
        first = self._read(source, x, y)
        self.page.wait_for_timeout(max(65, min(self.ms, 140)))
        second = self._read(source, x, y)
        # If a tooltip arrived between reads, allow one more settling read.
        if not first and second:
            self.page.wait_for_timeout(90)
            first, second = second, self._read(source, x, y)
        self.last_visible = second
        if second:
            self.diagnostics['hover_positions_with_visible_popups'] = self.diagnostics.get('hover_positions_with_visible_popups', 0) + 1
        stable = [hit for name, hit in second.items()
                  if name in first and _same(first[name], hit)]
        if not stable and second:
            self.diagnostics['unstable_popup_positions'] = self.diagnostics.get('unstable_popup_positions', 0) + 1
        fresh = []
        for hit in stable:
            before = previous.get(hit.section)
            # A tooltip that remained visible throughout the mouse movement is
            # not evidence of the hovered position. Do not fabricate a hit.
            if before and _signature(before) == _signature(hit):
                self.diagnostics['unchanged_popup_positions'] = self.diagnostics.get('unchanged_popup_positions', 0) + 1
                continue
            fresh.append(hit)
        if fresh:
            self.diagnostics['fresh_hover_positions'] = self.diagnostics.get('fresh_hover_positions', 0) + 1
        return fresh