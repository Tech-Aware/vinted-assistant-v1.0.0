# domain/json_utils.py

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Regex pour extraire un bloc ```json ... ```
JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def safe_json_parse(text: str) -> Dict[str, Any]:
    """
    Essaie de parser en JSON de manière ultra robuste.

    Stratégie :
    1) tentative directe json.loads
    2) extraction d'un bloc entre ```json ... ``` ou ``` ... ```
    3) fallback : on prend tout ce qui est entre le premier '{' et le dernier '}'
    4) sinon : ValueError
    """
    if text is None:
        raise ValueError("Texte JSON vide (None).")

    raw = text.strip()
    logger.debug("safe_json_parse: début, longueur=%d", len(raw))

    # 1) tentative directe
    try:
        parsed = json.loads(raw)
        logger.debug("safe_json_parse: parse direct OK (dict keys=%s)", list(parsed.keys()))
        return parsed
    except Exception:
        logger.debug("safe_json_parse: échec parse direct, on tente les fences markdown.")

    # 2) bloc ```json ... ``` ou ``` ... ```
    #    On cherche le contenu entre les fences, en capturant l'objet JSON.
    fence_pattern = re.compile(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    m = fence_pattern.search(raw)
    if m:
        inner = m.group(1).strip()
        logger.debug(
            "safe_json_parse: bloc markdown détecté, longueur inner=%d",
            len(inner),
        )
        try:
            parsed = json.loads(inner)
            logger.debug(
                "safe_json_parse: parse bloc markdown OK (dict keys=%s)",
                list(parsed.keys()),
            )
            return parsed
        except Exception as exc:
            logger.error(
                "safe_json_parse: échec parse bloc markdown: %s",
                exc,
            )

    # 3) fallback brutal : on prend du premier '{' au dernier '}'
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = raw[start : end + 1]
        logger.debug(
            "safe_json_parse: tentative fallback sur substring [%d:%d], longueur=%d",
            start,
            end,
            len(candidate),
        )
        try:
            parsed = json.loads(candidate)
            logger.debug(
                "safe_json_parse: parse fallback OK (dict keys=%s)",
                list(parsed.keys()),
            )
            return parsed
        except Exception as exc:
            logger.error(
                "safe_json_parse: échec parse fallback: %s",
                exc,
            )

    # 4) échec complet
    logger.error("Impossible de parser JSON brut. Contenu tronqué: %s", raw[:300])
    raise ValueError("JSON invalide ou introuvable dans le texte brut.")
