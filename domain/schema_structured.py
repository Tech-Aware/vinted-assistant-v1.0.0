# domain/schema_structured.py

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Sous-ensemble strict des mots-clés JSON Schema qu'on considère "safe" pour structured outputs.
# (On pourra élargir plus tard si besoin.)
_ALLOWED_KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "enum",
    "format",
    "minimum",
    "maximum",
    "title",
    "description",
}


def _walk_schema(schema: Any, path: str = "") -> List[Tuple[str, str]]:
    """
    Retourne une liste de (path, keyword) pour les mots-clés JSON Schema non supportés.
    Note: les noms des propriétés (dans 'properties') ne sont pas des keywords schema.
    """
    issues: List[Tuple[str, str]] = []

    if isinstance(schema, dict):
        for k, v in schema.items():
            here = f"{path}/{k}" if path else k

            # 'properties' contient des champs utilisateurs, pas des keywords schema
            if k == "properties" and isinstance(v, dict):
                for prop_name, prop_schema in v.items():
                    issues.extend(_walk_schema(prop_schema, f"{here}/{prop_name}"))
                continue

            # on ignore $schema s'il existe
            if k not in _ALLOWED_KEYS and k not in {"$schema"}:
                issues.append((here, k))

            issues.extend(_walk_schema(v, here))

    elif isinstance(schema, list):
        for i, item in enumerate(schema):
            issues.extend(_walk_schema(item, f"{path}[{i}]"))

    return issues


def _enforce_additional_properties_false(schema: Any, changes: List[str], path: str = "") -> None:
    """
    Ajoute additionalProperties:false sur tous les objets qui ont des 'properties' définies,
    si 'additionalProperties' n'est pas déjà présent.
    """
    if not isinstance(schema, dict):
        return

    schema_type = schema.get("type")
    props = schema.get("properties")
    has_props = isinstance(props, dict)

    if schema_type == "object" and has_props:
        if "additionalProperties" not in schema:
            schema["additionalProperties"] = False
            changes.append(f"{path or '<root>'}: additionalProperties=false")

    # Recurse dans properties
    if isinstance(props, dict):
        for prop_name, prop_schema in props.items():
            child_path = f"{path}/properties/{prop_name}" if path else f"properties/{prop_name}"
            _enforce_additional_properties_false(prop_schema, changes, child_path)

    # Recurse dans items / prefixItems
    if "items" in schema:
        _enforce_additional_properties_false(schema["items"], changes, f"{path}/items" if path else "items")

    if "prefixItems" in schema and isinstance(schema["prefixItems"], list):
        for i, item in enumerate(schema["prefixItems"]):
            _enforce_additional_properties_false(
                item,
                changes,
                f"{path}/prefixItems[{i}]" if path else f"prefixItems[{i}]",
            )


def make_structured_output_schema(
    schema: Dict[str, Any],
    *,
    schema_name: str = "unknown",
    enforce_no_extra_keys: bool = True,
    strict: bool = False,
) -> Tuple[Dict[str, Any], List[str], List[Tuple[str, str]]]:
    """
    Assainit un JSON Schema pour un usage 'structured outputs'.

    Retourne:
      - sanitized_schema (deepcopy)
      - changes (liste de modifications appliquées)
      - unsupported (liste des keywords non supportés: (path, keyword))

    Journalisation:
      - INFO: résumé des ajustements (si any)
      - WARNING: présence de keywords non supportés (si any)
      - DEBUG: détails (liste des changements + paths keyword)
    """
    if not isinstance(schema, dict):
        raise TypeError("schema must be a dict")

    sanitized: Dict[str, Any] = copy.deepcopy(schema)
    changes: List[str] = []

    unsupported = _walk_schema(sanitized)

    if enforce_no_extra_keys:
        _enforce_additional_properties_false(sanitized, changes)

    # Logs: résumé + détails (style projet)
    if changes:
        logger.info("Schema structured-ready (%s): %d ajustement(s).", schema_name, len(changes))
        logger.debug("Détails ajustements schema (%s): %s", schema_name, changes)
    else:
        logger.debug("Schema structured-ready (%s): aucun ajustement.", schema_name)

    if unsupported:
        uniq = sorted(set(k for _, k in unsupported))
        msg = f"Schema structured outputs: keywords non supportés ({schema_name}): {uniq}"
        if strict:
            logger.error(msg)
            raise ValueError(msg)
        logger.warning(msg)
        logger.debug("Détails keywords non supportés (%s): %s", schema_name, unsupported)
    else:
        logger.debug("Schema structured outputs (%s): aucun keyword non supporté détecté.", schema_name)

    return sanitized, changes, unsupported
