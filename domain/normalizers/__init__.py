# domain/normalizers/__init__.py

"""
Package de normalisation pour les differents profils d'analyse.

Ce package contient les builders de features et les utilitaires de normalisation
pour chaque type de vetement (jeans Levi's, pulls, vestes Carhartt, etc.).
"""

from domain.normalizers.base import (
    ALIASES,
    REQUIRED_KEYS,
    FEATURE_DEFAULTS,
    normalize_listing,
    coerce_profile_name,
    apply_feature_defaults,
    normalize_tommy_brand,
    normalize_pull_brand,
    normalize_sizes,
)

from domain.normalizers.jean_levis import build_features_for_jean_levis
from domain.normalizers.pull import build_features_for_pull, build_features_for_pull_tommy
from domain.normalizers.jacket_carhart import build_features_for_jacket_carhart

from domain.normalizers.text_extractors import (
    strip_parentheses_notes,
    strip_composition_prefixes,
    strip_leading_keyword,
    extract_model_from_text,
    normalize_sku_value,
    normalize_jcr_sku,
    looks_like_carhartt_sku,
    extract_fit_from_text,
    normalize_fit_label,
    extract_color_from_text,
    extract_sizes_from_text,
    extract_carhartt_model_from_text,
    normalize_carhartt_model,
    detect_flag_from_text,
    detect_chest_pocket_from_text,
    extract_lining_from_text,
    extract_segment_with_composition,
    extract_body_lining_composition,
    extract_exterior_from_text,
    extract_sleeve_lining_from_text,
    extract_closure_from_text,
    extract_patch_material_from_text,
    extract_collar_from_text,
    extract_zip_material_from_text,
    extract_origin_country_from_text,
    extract_carhartt_composition_from_ocr_structured,
    split_carhartt_composition_blocks,
)

__all__ = [
    # Base
    "ALIASES",
    "REQUIRED_KEYS",
    "FEATURE_DEFAULTS",
    "normalize_listing",
    "coerce_profile_name",
    "apply_feature_defaults",
    "normalize_tommy_brand",
    "normalize_pull_brand",
    "normalize_sizes",
    # Profile builders
    "build_features_for_jean_levis",
    "build_features_for_pull",
    "build_features_for_pull_tommy",  # Alias pour retrocompatibilite
    "build_features_for_jacket_carhart",
    # Text extractors
    "strip_parentheses_notes",
    "strip_composition_prefixes",
    "strip_leading_keyword",
    "extract_model_from_text",
    "normalize_sku_value",
    "normalize_jcr_sku",
    "looks_like_carhartt_sku",
    "extract_fit_from_text",
    "normalize_fit_label",
    "extract_color_from_text",
    "extract_sizes_from_text",
    "extract_carhartt_model_from_text",
    "normalize_carhartt_model",
    "detect_flag_from_text",
    "detect_chest_pocket_from_text",
    "extract_lining_from_text",
    "extract_segment_with_composition",
    "extract_body_lining_composition",
    "extract_exterior_from_text",
    "extract_sleeve_lining_from_text",
    "extract_closure_from_text",
    "extract_patch_material_from_text",
    "extract_collar_from_text",
    "extract_zip_material_from_text",
    "extract_origin_country_from_text",
    "extract_carhartt_composition_from_ocr_structured",
    "split_carhartt_composition_blocks",
]
