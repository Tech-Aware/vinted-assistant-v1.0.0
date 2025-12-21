# domain/ocr_models.py

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any


@dataclass
class OCRCompositionItem:
    material: str
    percent: Optional[int]


@dataclass
class OCRStructured:
    size_candidates: List[str]
    composition_items: List[OCRCompositionItem]
    origin: Optional[str]
    sku_candidates: List[str]
    filtered_text: str
    debug_lines: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size_candidates": list(self.size_candidates),
            "composition_items": [
                asdict(item) for item in self.composition_items
            ],
            "origin": self.origin,
            "sku_candidates": list(self.sku_candidates),
            "filtered_text": self.filtered_text,
            "debug_lines": list(self.debug_lines),
        }
