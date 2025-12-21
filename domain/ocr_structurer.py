# domain/ocr_structurer.py

from __future__ import annotations

import logging
import re
from typing import List, Optional, Sequence, Tuple

from domain.ocr_models import OCRCompositionItem, OCRStructured

logger = logging.getLogger(__name__)


class StructuredOCRExtractor:
    """
    Extracteur textuel qui filtre et structure un OCR bruité.
    Utilise des regex + heuristiques pour ne garder que les informations clés.
    """

    _MATERIAL_ALIASES = {
        "COTON": "coton",
        "COTTON": "coton",
        "POLYESTER": "polyester",
        "PES": "polyester",
        "POLYAMIDE": "polyamide",
        "NYLON": "nylon",
        "ACRYLIQUE": "acrylique",
        "ACRYLIC": "acrylique",
        "VISCOSE": "viscose",
        "ELASTANE": "élasthanne",
        "ELASTHANNE": "élasthanne",
        "SPANDEX": "élasthanne",
        "LYCRA": "élasthanne",
        "ELAST": "élasthanne",
        "LINEN": "lin",
        "LIN": "lin",
        "SOIE": "soie",
        "SILK": "soie",
        "WOOL": "laine",
        "LAINE": "laine",
        "CACHEMIRE": "cachemire",
        "CASHMERE": "cachemire",
    }

    _SIZE_REGEX = re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|XXXL)\b", re.IGNORECASE)
    _JEANS_REGEX = re.compile(
        r"\b(?:W\s?\d{2}\b|\d{2}\s?W\b|L\s?\d{2}\b|\d{2}\s?L\b|W\d{2}\s*L\d{2})",
        re.IGNORECASE,
    )
    _EU_REGEX = re.compile(r"\b(?:EU|FR)\s?\d{2}\b", re.IGNORECASE)
    _ORIGIN_REGEX = re.compile(
        r"(MADE\s*IN|MADEIN|FABRIQU[ÉE]\s*EN)\s+([A-ZÀ-ÖØ-ß\s]+)", re.IGNORECASE
    )
    _PERCENT_MATERIAL = re.compile(
        r"(?P<percent>\d{1,3})\s*%?\s*(?P<material>[A-ZÀ-ÖØ-ß]+)", re.IGNORECASE
    )
    _MATERIAL_PERCENT = re.compile(
        r"(?P<material>[A-ZÀ-ÖØ-ß]+)\s*(?P<percent>\d{1,3})\s*%?", re.IGNORECASE
    )
    _SKU_REGEXES = [
        re.compile(r"\b(?:RN|CA)\s?\d+\b", re.IGNORECASE),
        re.compile(r"\bSTYLE[:\s]+[A-Z0-9-]+\b", re.IGNORECASE),
        re.compile(r"\bREF[:\s]+[A-Z0-9-]+\b", re.IGNORECASE),
        re.compile(r"\bJCR\d+\b", re.IGNORECASE),
        re.compile(r"\b[A-Z0-9-]{4,20}\b", re.IGNORECASE),
    ]

    _SEPARATOR_SANITIZER = re.compile(r"[|·•]+")

    def structure(self, raw_text: str) -> OCRStructured:
        normalized_lines = self._normalize_lines(raw_text)
        filtered_lines = self._filter_relevant_lines(normalized_lines)
        composition = self._extract_composition(filtered_lines)
        sizes = self._extract_sizes(filtered_lines)
        origin = self._extract_origin(filtered_lines)
        sku_candidates = self._extract_skus(filtered_lines)

        filtered_text = self._build_filtered_text(
            sizes=sizes,
            composition=composition,
            origin=origin,
            sku_candidates=sku_candidates,
            kept_lines=filtered_lines,
        )

        logger.debug(
            "StructuredOCRExtractor: %d ligne(s) retenues, %d item(s) composition, %d taille(s), %d SKU(s).",
            len(filtered_lines),
            len(composition),
            len(sizes),
            len(sku_candidates),
        )

        return OCRStructured(
            size_candidates=sizes,
            composition_items=composition,
            origin=origin,
            sku_candidates=sku_candidates,
            filtered_text=filtered_text,
            debug_lines=filtered_lines,
        )

    def _normalize_lines(self, raw_text: str) -> List[str]:
        text = (raw_text or "").replace("％", "%")
        text = self._SEPARATOR_SANITIZER.sub(" ", text)
        text = re.sub(r"[\/]", " / ", text)

        lines: List[str] = []
        for line in text.splitlines():
            compact = re.sub(r"\s+", " ", line).strip()
            if compact:
                lines.append(compact.upper())

        logger.debug(
            "StructuredOCRExtractor._normalize_lines: %d ligne(s) après normalisation.",
            len(lines),
        )
        return lines

    def _filter_relevant_lines(self, lines: Sequence[str]) -> List[str]:
        kept: List[str] = []
        for line in lines:
            if self._is_composition_line(line) or self._is_size_line(line) or self._is_origin_line(line) or self._is_sku_line(line):
                if line not in kept:
                    kept.append(line)
        logger.debug("StructuredOCRExtractor._filter_relevant_lines: %d/%d ligne(s) conservées.", len(kept), len(lines))
        return kept

    def _is_composition_line(self, line: str) -> bool:
        if "%" in line:
            return True
        return any(alias in line for alias in self._MATERIAL_ALIASES)

    def _is_size_line(self, line: str) -> bool:
        return bool(self._SIZE_REGEX.search(line) or self._JEANS_REGEX.search(line) or self._EU_REGEX.search(line))

    def _is_origin_line(self, line: str) -> bool:
        return "MADE IN" in line or "MADEIN" in line or "FABRIQU" in line

    def _is_sku_line(self, line: str) -> bool:
        return any(regex.search(line) for regex in self._SKU_REGEXES[:4])

    def _extract_sizes(self, lines: Sequence[str]) -> List[str]:
        found: List[str] = []
        for line in lines:
            for regex in (self._SIZE_REGEX, self._JEANS_REGEX, self._EU_REGEX):
                for match in regex.findall(line):
                    value = match if isinstance(match, str) else "".join(match)
                    normalized = re.sub(r"\s+", " ", value.strip())
                    if normalized and normalized.upper() not in (v.upper() for v in found):
                        found.append(normalized)
            waist = re.search(r"W\s?\d{2}", line, re.IGNORECASE)
            length = re.search(r"L\s?\d{2}", line, re.IGNORECASE)
            if waist and length:
                combined = f"{waist.group().replace(' ', '')} {length.group().replace(' ', '')}"
                if combined.upper() not in (v.upper() for v in found):
                    found.append(combined)
        return found

    def _extract_origin(self, lines: Sequence[str]) -> Optional[str]:
        for line in lines:
            match = self._ORIGIN_REGEX.search(line)
            if match:
                country = match.group(2).strip()
                country = re.sub(r"\s+", " ", country)
                return f"Made in {country.title()}"
        return None

    def _extract_composition(self, lines: Sequence[str]) -> List[OCRCompositionItem]:
        items: List[OCRCompositionItem] = []
        for line in lines:
            if not self._is_composition_line(line):
                continue
            matches = list(self._iter_material_matches(line))
            for percent, material in matches:
                if material and 0 <= percent <= 100:
                    if not any(i.material == material and i.percent == percent for i in items):
                        items.append(OCRCompositionItem(material=material, percent=percent))
        return items

    def _iter_material_matches(self, line: str):
        for regex in (self._PERCENT_MATERIAL, self._MATERIAL_PERCENT):
            for match in regex.finditer(line):
                percent_raw = match.group("percent")
                material_raw = match.group("material")
                material = self._canonical_material(material_raw)
                try:
                    percent = int(percent_raw)
                except Exception:
                    continue
                percent = max(0, min(100, percent))
                yield percent, material

    def _canonical_material(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        key = raw.upper()
        return self._MATERIAL_ALIASES.get(key)

    def _extract_skus(self, lines: Sequence[str]) -> List[str]:
        candidates: List[str] = []
        for line in lines:
            for regex in self._SKU_REGEXES:
                for match in regex.findall(line):
                    value = match if isinstance(match, str) else "".join(match)
                    cleaned = value.replace(" ", "").replace(":", "")
                    if 4 <= len(cleaned) <= 20 and any(ch.isdigit() for ch in cleaned):
                        if cleaned.upper() not in (c.upper() for c in candidates):
                            candidates.append(cleaned)
        return candidates

    def _build_filtered_text(
        self,
        *,
        sizes: Sequence[str],
        composition: Sequence[OCRCompositionItem],
        origin: Optional[str],
        sku_candidates: Sequence[str],
        kept_lines: Sequence[str],
    ) -> str:
        lines: List[str] = ["[OCR_CADRÉ]"]
        lines.append("SIZE:")
        if sizes:
            lines.extend(f"- {size}" for size in sizes)
        else:
            lines.append("- (none)")

        lines.append("")
        lines.append("COMPOSITION:")
        if composition:
            for item in composition:
                if item.percent is not None:
                    lines.append(f"- {item.percent}% {item.material}")
                else:
                    lines.append(f"- {item.material}")
        else:
            lines.append("- (none)")

        lines.append("")
        lines.append("ORIGIN:")
        lines.append(f"- {origin}" if origin else "- (none)")

        lines.append("")
        lines.append("SKU/CODES:")
        if sku_candidates:
            lines.extend(f"- {sku}" for sku in sku_candidates)
        else:
            lines.append("- (none)")

        lines.append("")
        lines.append("LIGNES RETENUES:")
        if kept_lines:
            lines.extend(f"- {line}" for line in kept_lines)
        else:
            lines.append("- (none)")

        return "\n".join(lines)
