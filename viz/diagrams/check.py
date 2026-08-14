#!/usr/bin/env python3
"""Validate static Microdata Lab diagram HTML.

The contract is adapted from Cathryn Lavery's diagram-design self-check
(MIT, version 2.3). It intentionally supports static, single-SVG artifacts
only; motion belongs in the chart media pipeline.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

FORBIDDEN_TAGS = {"base", "embed", "iframe", "object", "script"}
REFERENCE_ATTRS = {"action", "formaction", "href", "poster", "src", "srcdoc", "xlink:href"}
REMOTE_RE = re.compile(r"(?:https?:)?//", re.IGNORECASE)
FORBIDDEN_CSS = ("box-shadow", "drop-shadow", "linear-gradient", "radial-gradient")


class DiagramParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.references: list[tuple[str, str, str]] = []
        self.styles: list[str] = []
        self.svgs: list[dict[str, object]] = []
        self.ids: list[str] = []
        self.lines: list[dict[str, str]] = []
        self._svg_depth = 0
        self._svg: dict[str, object] | None = None
        self._capture: str | None = None
        self._style_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        data = {key.casefold(): value or "" for key, value in attrs}
        if tag in FORBIDDEN_TAGS:
            self.errors.append(f"<{tag}> is not allowed")
        for key, value in data.items():
            if key.startswith("on"):
                self.errors.append(f"executable attribute {key} on <{tag}>")
            if key in REFERENCE_ATTRS:
                self.references.append((tag, data.get("rel", ""), value))
        if identifier := data.get("id"):
            self.ids.append(identifier)
        if tag == "style":
            self._style_depth += 1
        if tag == "line":
            self.lines.append(data)
        if tag == "svg" and self._svg_depth == 0:
            self._svg_depth = 1
            self._svg = {"attrs": data, "first": None, "title": {}, "desc": {}}
            self.svgs.append(self._svg)
            return
        if self._svg_depth:
            self._svg_depth += 1
            assert self._svg is not None
            if self._svg_depth == 2 and self._svg["first"] is None:
                self._svg["first"] = tag
            if self._svg_depth == 2 and tag in {"title", "desc"}:
                self._svg[tag] = {"attrs": data, "text": ""}
                self._capture = tag

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "style":
            self._style_depth = max(0, self._style_depth - 1)
        if self._svg_depth:
            if tag in {"title", "desc"}:
                self._capture = None
            self._svg_depth -= 1
            if self._svg_depth == 0:
                self._svg = None

    def handle_data(self, data: str) -> None:
        if self._style_depth:
            self.styles.append(data)
        if self._capture and self._svg is not None:
            node = self._svg[self._capture]
            assert isinstance(node, dict)
            node["text"] = str(node.get("text", "")) + data


def reference_error(tag: str, rel: str, value: str) -> str | None:
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    parsed = urlparse(value)
    if not (parsed.scheme or value.startswith("//")):
        return None
    if (
        tag == "link"
        and "stylesheet" in rel.casefold().split()
        and parsed.scheme == "https"
        and parsed.hostname == "fonts.googleapis.com"
        and parsed.path == "/css2"
    ):
        return None
    return f"remote reference on <{tag}>: {value[:100]}"


def check(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    parser = DiagramParser()
    parser.feed(source)
    parser.close()
    errors = list(parser.errors)
    if len(parser.svgs) != 1:
        errors.append(f"expected exactly one SVG; found {len(parser.svgs)}")
    for index, svg in enumerate(parser.svgs, 1):
        attrs = svg["attrs"]
        title = svg["title"]
        desc = svg["desc"]
        assert isinstance(attrs, dict) and isinstance(title, dict) and isinstance(desc, dict)
        if attrs.get("role") != "img":
            errors.append(f"svg {index} needs role=img")
        if not attrs.get("viewbox"):
            errors.append(f"svg {index} needs a viewBox")
        if svg["first"] != "title":
            errors.append(f"svg {index} title must be its first child")
        title_attrs = title.get("attrs", {})
        desc_attrs = desc.get("attrs", {})
        assert isinstance(title_attrs, dict) and isinstance(desc_attrs, dict)
        title_id = str(title_attrs.get("id", ""))
        desc_id = str(desc_attrs.get("id", ""))
        if not title_id or title_id == "title" or not desc_id or desc_id == "desc":
            errors.append(f"svg {index} title/desc IDs must be diagram-prefixed")
        if attrs.get("aria-labelledby", "").split() != [title_id, desc_id]:
            errors.append(f"svg {index} aria-labelledby must name title then desc")
        if not str(title.get("text", "")).strip() or not str(desc.get("text", "")).strip():
            errors.append(f"svg {index} needs non-empty title and desc")
    duplicates = sorted(
        {identifier for identifier in parser.ids if parser.ids.count(identifier) > 1}
    )
    if duplicates:
        errors.append(f"duplicate IDs: {', '.join(duplicates)}")
    for tag, rel, value in parser.references:
        if error := reference_error(tag, rel, value):
            errors.append(error)
    css = "\n".join(parser.styles).casefold()
    for forbidden in FORBIDDEN_CSS:
        if forbidden in css:
            errors.append(f"forbidden CSS treatment: {forbidden}")
    if REMOTE_RE.search(css):
        errors.append("remote URL inside CSS; use repository-local assets")
    for index, line in enumerate(parser.lines, 1):
        try:
            x1, x2 = float(line["x1"]), float(line["x2"])
            y1, y2 = float(line["y1"]), float(line["y2"])
        except (KeyError, ValueError):
            continue
        if x1 != x2 and y1 != y2:
            errors.append(f"line {index} is diagonal; use an orthogonal path")
    if 'data-diagram-design-version="2.3"' not in source:
        errors.append("missing pinned diagram-design version metadata")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    errors = check(args.html)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print(f"OK {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
