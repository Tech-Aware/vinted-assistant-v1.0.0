from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


logger = logging.getLogger(__name__)


@dataclass
class TitleRules:
    """Règles transverses appliquées à tous les titres."""

    max_length: int = 100
    separator: str = " "
    max_colors: int = 2
    capitalize_before_size: bool = True
    capitalize_after_size: bool = False
    material_priority: tuple[str, ...] = (
        "cachemire",
        "angora",
        "laine",
        "coton",
    )


@dataclass
class TitleBlock:
    """Un bloc élémentaire du titre (catégorie, marque, taille…)."""

    kind: str
    value: str
    trim_priority: int = 1
    capitalize: Optional[bool] = None
    critical: bool = False

    def formatted_value(self, should_capitalize: bool) -> str:
        if not should_capitalize:
            return self.value.strip()
        words = [token for token in self.value.strip().split(" ") if token]
        return " ".join(word.capitalize() for word in words)


@dataclass
class TitleSpec:
    name: str
    order: List[str]
    size_kinds: List[str] = field(default_factory=list)


def _sanitize_blocks(blocks: Iterable[TitleBlock]) -> List[TitleBlock]:
    sanitized: List[TitleBlock] = []
    for block in blocks:
        if not block or not isinstance(block, TitleBlock):
            logger.debug("_sanitize_blocks: bloc ignoré (type inattendu)")
            continue
        value = block.value.strip()
        if not value:
            logger.debug("_sanitize_blocks: bloc %s vide, ignoré", block.kind)
            continue
        sanitized.append(TitleBlock(**{**block.__dict__, "value": value}))
    return sanitized


def _limit_colors(blocks: List[TitleBlock], max_colors: int) -> List[TitleBlock]:
    kept: List[TitleBlock] = []
    color_seen = 0
    for block in blocks:
        if block.kind.startswith("color"):
            if color_seen >= max_colors:
                logger.info(
                    "_limit_colors: couleur ignorée (dépassement max %s): %s",
                    max_colors,
                    block.value,
                )
                continue
            color_seen += 1
        kept.append(block)
    return kept


def _select_main_material(candidates: Iterable[str], rules: TitleRules) -> Optional[str]:
    material_list = [str(item).strip() for item in candidates if str(item).strip()]
    for priority in rules.material_priority:
        for candidate in material_list:
            if priority in candidate.lower():
                if re.search(r"\d+\s*%", candidate):
                    logger.debug(
                        "_select_main_material: matière prioritaire retenue avec pourcentage (%s)",
                        candidate,
                    )
                    return candidate
                logger.debug(
                    "_select_main_material: matière prioritaire %s retenue depuis %s",
                    priority,
                    candidate,
                )
                return priority
    if material_list:
        logger.debug(
            "_select_main_material: première matière non prioritaire retenue (%s)",
            material_list[0],
        )
        return material_list[0]
    return None


def _trim_to_length(blocks: List[TitleBlock], rules: TitleRules) -> List[TitleBlock]:
    ordered_blocks = list(blocks)
    while True:
        assembled = rules.separator.join(token.value for token in ordered_blocks)
        if len(assembled) <= rules.max_length:
            return ordered_blocks

        removable_candidates = [
            (idx, block)
            for idx, block in enumerate(ordered_blocks)
            if not block.critical and block.trim_priority > 0
        ]
        if not removable_candidates:
            logger.warning(
                "_trim_to_length: aucun bloc supprimable malgré un titre trop long (%s)",
                len(assembled),
            )
            return ordered_blocks

        idx_to_remove, block_to_remove = max(
            removable_candidates, key=lambda item: (item[1].trim_priority, item[0])
        )
        logger.info(
            "_trim_to_length: suppression du bloc '%s' pour respecter %s caractères",
            block_to_remove.value,
            rules.max_length,
        )
        ordered_blocks.pop(idx_to_remove)


def render_title(blocks: Iterable[TitleBlock], spec: TitleSpec, rules: Optional[TitleRules] = None) -> str:
    """
    Rend un titre ordonné à partir d'une liste de blocs en appliquant les règles
    transverses (couleurs max 2, capitalisation, limite de longueur…).
    """

    active_rules = rules or TitleRules()
    sanitized_blocks = _sanitize_blocks(blocks)
    sanitized_blocks = _limit_colors(sanitized_blocks, active_rules.max_colors)

    blocks_by_kind: Dict[str, List[TitleBlock]] = {}
    for block in sanitized_blocks:
        blocks_by_kind.setdefault(block.kind, []).append(block)

    ordered: List[TitleBlock] = []
    size_seen = False
    for kind in spec.order:
        for block in blocks_by_kind.get(kind, []):
            capitalize_flag = block.capitalize
            if capitalize_flag is None:
                if size_seen:
                    capitalize_flag = active_rules.capitalize_after_size
                else:
                    capitalize_flag = active_rules.capitalize_before_size
            formatted_value = block.formatted_value(capitalize_flag)
            ordered.append(
                TitleBlock(
                    kind=block.kind,
                    value=formatted_value,
                    trim_priority=block.trim_priority,
                    capitalize=capitalize_flag,
                    critical=block.critical,
                )
            )
            if kind in spec.size_kinds:
                size_seen = True

    trimmed_blocks = _trim_to_length(ordered, active_rules)
    final_title = active_rules.separator.join(block.value for block in trimmed_blocks)
    logger.debug("render_title: titre final='%s'", final_title)
    return final_title


# Spécifications de catégories -------------------------------------------------


class JeanSpec(TitleSpec):
    def __init__(self) -> None:
        super().__init__(
            name="jean",
            order=[
                "category",
                "brand",
                "model",
                "premium",
                "size",
                "fit",
                "stretch",
                "material",
                "color_primary",
                "color_secondary",
                "gender",
                "sku",
            ],
            size_kinds=["size"],
        )


class PullGiletSpec(TitleSpec):
    def __init__(self) -> None:
        super().__init__(
            name="pull_gilet",
            order=[
                "category",
                "brand",
                "premium",
                "pattern",
                "size",
                "color_primary",
                "color_secondary",
                "material",
                "neckline",
                "gender",
                "specificity",
                "sku",
            ],
            size_kinds=["size"],
        )


class JacketSpec(TitleSpec):
    def __init__(self) -> None:
        super().__init__(
            name="jacket",
            order=[
                "category",
                "brand",
                "style",
                "size",
                "specificities",
                "material",
                "color_primary",
                "color_secondary",
                "gender",
                "sku",
            ],
            size_kinds=["size"],
        )


def build_material_block(values: Iterable[str], rules: Optional[TitleRules] = None) -> Optional[TitleBlock]:
    active_rules = rules or TitleRules()
    main_material = _select_main_material(values, active_rules)
    if not main_material:
        return None
    return TitleBlock(kind="material", value=main_material, trim_priority=2)
