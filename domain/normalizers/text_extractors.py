# domain/normalizers/text_extractors.py

"""
Utilitaires d'extraction de texte pour les normalizers.

Ce module contient les fonctions qui extraient des informations
(modèle, couleur, composition, etc.) à partir de textes libres.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utilitaires de nettoyage de texte
# ---------------------------------------------------------------------------

def strip_parentheses_notes(s: Optional[str]) -> Optional[str]:
    """Enlève les notes entre parenthèses."""
    if not s:
        return s
    return re.sub(r"\s*\([^)]*\)\s*", " ", str(s)).strip()


def strip_composition_prefixes(s: Optional[str]) -> Optional[str]:
    """Supprime les préfixes redondants de composition."""
    if not s:
        return s
    txt = str(s).strip()
    txt = re.sub(r"(?i)^\s*[-•]?\s*(mati[eè]re\s+)?(ext[eé]rieur|exterior|shell)\s*[:\-–]\s*", "", txt).strip()
    txt = re.sub(r"(?i)^\s*[-•]?\s*(doublure|lining|body\s+lining)\s*[:\-–]\s*", "", txt).strip()
    txt = re.sub(r"(?i)^\s*[-•]?\s*(doublure\s+des\s+manches|manches|sleeve\s+lining)\s*[:\-–]\s*", "", txt).strip()
    return txt


def strip_leading_keyword(segment: str, keywords: tuple[str, ...]) -> str:
    """Enlève les mots-clés en début de segment."""
    try:
        if not segment:
            return ""
        result = segment
        for keyword in keywords:
            pattern = rf"^\s*{keyword}\s*[:\-–]?\s*"
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        return result.strip()
    except Exception as exc:
        logger.debug("strip_leading_keyword: nettoyage impossible (%s)", exc)
        return segment


# ---------------------------------------------------------------------------
# Extraction de modèles et SKU
# ---------------------------------------------------------------------------

def extract_model_from_text(text: str) -> Optional[str]:
    """Extrait un modèle Levi's (ex: 501, 511, 515) depuis du texte."""
    if not text:
        return None
    match = re.search(r"\b5\d{2}\b", text)
    if match:
        return match.group(0)
    return None


def normalize_sku_value(value: Any) -> Optional[str]:
    """Normalise un SKU en supprimant les placeholders issus de l'IA."""
    if value is None:
        return None
    try:
        s = str(value).strip()
    except Exception:
        return None
    if not s:
        return None
    low = s.lower()
    if low in {"null", "none", "n/a", "na", "nc", "unknown", "missing", "?"}:
        logger.debug("normalize_sku_value: placeholder détecté (%r) -> None", s)
        return None
    return s


def normalize_jcr_sku(raw: Optional[Any]) -> Optional[str]:
    """Normalise un SKU Carhartt interne de type JCR + digits."""
    try:
        if raw is None:
            return None
        txt = str(raw).strip()
        if not txt:
            return None
        m = re.search(r"\bJCR\s*0*(\d+)\b", txt, flags=re.IGNORECASE)
        if not m:
            return None
        num = m.group(1)
        try:
            num_int = int(num)
            if num_int <= 0:
                return None
            return f"JCR{num_int}"
        except ValueError:
            return f"JCR{num}"
    except Exception as exc:
        logger.debug("normalize_jcr_sku: normalisation impossible (%s)", exc)
        return None


def looks_like_carhartt_sku(token: str) -> bool:
    """Repère un code produit (EJ001, BLK, etc.) pour l'ignorer du modèle."""
    try:
        if not token:
            return False
        cleaned = token.strip()
        if len(cleaned) < 3:
            return False
        has_digit = any(char.isdigit() for char in cleaned)
        has_upper = any(char.isupper() for char in cleaned)
        if has_digit and has_upper and re.fullmatch(r"[A-Za-z0-9]+", cleaned):
            logger.debug("looks_like_carhartt_sku: token '%s' considéré comme SKU", cleaned)
            return True
        if cleaned.isupper() and has_digit:
            return True
        return False
    except Exception as exc:
        logger.debug("looks_like_carhartt_sku: détection impossible (%s)", exc)
        return False


# ---------------------------------------------------------------------------
# Extraction de coupes (fit)
# ---------------------------------------------------------------------------

def extract_fit_from_text(text: str) -> Optional[str]:
    """Extrait la coupe (fit) depuis le texte."""
    if not text:
        return None
    low = text.lower()
    if "boot cut" in low or "bootcut" in low:
        return "Boot Cut/Évasé"
    return None


def normalize_fit_label(raw_fit: Optional[str]) -> Optional[str]:
    """Uniformise les libellés de coupe."""
    if not raw_fit:
        return None
    low = str(raw_fit).lower().strip()
    boot_markers = {"boot cut", "bootcut", "boot-cut", "flare", "curve", "curvy"}
    if any(marker in low for marker in boot_markers):
        return "Boot Cut/Évasé"
    if "skinny" in low or "slim" in low:
        return "Skinny"
    if "straight" in low or "droit" in low:
        return "Straight/Droit"
    return raw_fit


# ---------------------------------------------------------------------------
# Extraction de couleurs
# ---------------------------------------------------------------------------

def extract_color_from_text(text: str) -> Optional[str]:
    """Extrait une couleur simple depuis le texte."""
    if not text:
        return None
    low = text.lower()
    if "bleu délavé" in low:
        return "bleu délavé"
    if "bleu clair" in low:
        return "bleu clair"
    if "bleu foncé" in low:
        return "bleu foncé"
    if "bleu" in low:
        return "bleu"
    return None


# ---------------------------------------------------------------------------
# Extraction de tailles
# ---------------------------------------------------------------------------

def extract_sizes_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extrait (size_us, length) à partir d'un texte contenant des W/L."""
    if not text:
        return None, None
    compact = text.upper().replace(" ", "")
    w_match = re.search(r"W(\d+)", compact)
    l_match = re.search(r"L(\d+)", compact)
    size_us = f"W{w_match.group(1)}" if w_match else None
    length = f"L{l_match.group(1)}" if l_match else None
    return size_us, length


# ---------------------------------------------------------------------------
# Extraction de modèles Carhartt
# ---------------------------------------------------------------------------

def extract_carhartt_model_from_text(text: str) -> Optional[str]:
    """Détecte quelques modèles Carhartt courants à partir du texte libre."""
    try:
        if not text:
            return None
        low = text.lower()
        known_models = (
            "detroit", "active", "arctic", "michigan", "nimbus",
            "og", "new york", "ny", "trapper", "chore",
        )
        for model in known_models:
            if model in low:
                logger.info("extract_carhartt_model_from_text: modèle détecté (%s)", model)
                return model.title()
        return None
    except Exception as exc:
        logger.warning("extract_carhartt_model_from_text: détection impossible (%s)", exc)
        return None


def normalize_carhartt_model(raw_model: Optional[str], fallback_text: str) -> Optional[str]:
    """Nettoie le modèle Carhartt pour éviter l'affichage de codes produits."""
    try:
        if not raw_model:
            return extract_carhartt_model_from_text(fallback_text)
        tokens = re.split(r"[\s\-_/]+", raw_model.strip())
        filtered_tokens = [token for token in tokens if not looks_like_carhartt_sku(token)]
        if not filtered_tokens:
            logger.info("normalize_carhartt_model: modèle brut '%s' ignoré (SKU détecté)", raw_model)
            return extract_carhartt_model_from_text(fallback_text)
        candidate = " ".join(filtered_tokens).strip()
        if not candidate:
            return extract_carhartt_model_from_text(fallback_text)
        logger.debug("normalize_carhartt_model: modèle retenu '%s'", candidate)
        return candidate.title()
    except Exception as exc:
        logger.warning("normalize_carhartt_model: normalisation impossible (%s)", exc)
        return extract_carhartt_model_from_text(fallback_text)


# ---------------------------------------------------------------------------
# Détection de flags booléens
# ---------------------------------------------------------------------------

def detect_flag_from_text(text: str, keywords: tuple[str, ...]) -> Optional[bool]:
    """Détecte la présence d'un ou plusieurs mots-clés dans le texte."""
    try:
        if not text:
            return None
        low = text.lower()
        return any(keyword in low for keyword in keywords)
    except Exception as exc:
        logger.debug("detect_flag_from_text: analyse impossible (%s)", exc)
        return None


def detect_chest_pocket_from_text(text: str) -> Optional[bool]:
    """Détecte la présence d'une poche poitrine."""
    try:
        if not text:
            return None
        low = text.lower()
        markers = ("poche poitrine", "poche sur la poitrine", "poche avant")
        detected = any(marker in low for marker in markers)
        if detected:
            logger.debug("detect_chest_pocket_from_text: poche poitrine détectée")
            return True
        return None
    except Exception as exc:
        logger.debug("detect_chest_pocket_from_text: détection impossible (%s)", exc)
        return None


# ---------------------------------------------------------------------------
# Extraction de compositions et doublures
# ---------------------------------------------------------------------------

def extract_lining_from_text(text: str) -> Optional[str]:
    """Extrait le type de doublure depuis le texte."""
    try:
        if not text:
            return None
        low = text.lower()
        if "sherpa" in low:
            return "doublure sherpa"
        if "matelass" in low:
            return "doublure matelassée"
        if "polar" in low:
            return "doublure polaire"
        if "doubl" in low:
            return "doublure textile"
        return None
    except Exception as exc:
        logger.debug("extract_lining_from_text: extraction impossible (%s)", exc)
        return None


def extract_segment_with_composition(text: str, keywords: tuple[str, ...]) -> Optional[str]:
    """Extrait un segment contenant des compositions (100 %) associé à un mot-clé."""
    try:
        if not text:
            return None
        lowered = text.lower()
        if not any(keyword in lowered for keyword in keywords):
            return None
        candidates = re.split(r"[\n\.?!]", text)
        for segment in candidates:
            if not segment:
                continue
            if any(keyword in segment.lower() for keyword in keywords):
                cleaned = segment.strip(" ,;:\n")
                if cleaned:
                    return cleaned
        return None
    except Exception as exc:
        logger.debug("extract_segment_with_composition: extraction échouée (%s)", exc)
        return None


def extract_body_lining_composition(text: str) -> Optional[str]:
    """Extrait la composition de la doublure du corps."""
    try:
        segment = extract_segment_with_composition(
            text, ("doublure", "interieur", "intérieur")
        )
        if not segment:
            return None
        cleaned = strip_leading_keyword(
            segment, ("doublure", "interieur", "intérieur", "intérieur du corps")
        )
        logger.info("extract_body_lining_composition: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:
        logger.debug("extract_body_lining_composition: échec (%s)", exc)
        return None


def extract_exterior_from_text(text: str) -> Optional[str]:
    """Extrait la composition extérieure."""
    try:
        segment = extract_segment_with_composition(
            text, ("exterieur", "extérieur", "exterior")
        )
        if not segment:
            return None
        cleaned = strip_leading_keyword(
            segment, ("exterieur", "extérieur", "exterior")
        )
        logger.info("extract_exterior_from_text: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:
        logger.debug("extract_exterior_from_text: échec (%s)", exc)
        return None


def extract_sleeve_lining_from_text(text: str) -> Optional[str]:
    """Extrait la composition de la doublure des manches."""
    try:
        segment = extract_segment_with_composition(
            text, ("doublure des manches", "manches doubl", "sleeve lining")
        )
        if not segment:
            return None
        cleaned = strip_leading_keyword(
            segment, ("doublure des manches", "manches doubl", "sleeve lining")
        )
        logger.info("extract_sleeve_lining_from_text: segment détecté = %s", cleaned)
        return cleaned
    except Exception as exc:
        logger.debug("extract_sleeve_lining_from_text: échec (%s)", exc)
        return None


def extract_closure_from_text(text: str) -> Optional[str]:
    """Extrait le type de fermeture."""
    try:
        if not text:
            return None
        low = text.lower()
        if "double zip" in low or "double zipper" in low:
            return "double zip"
        if "zip" in low:
            return "zip"
        if "pression" in low:
            return "boutons pression"
        if "bouton" in low:
            return "boutons"
        return None
    except Exception as exc:
        logger.debug("extract_closure_from_text: extraction impossible (%s)", exc)
        return None


def extract_patch_material_from_text(text: str) -> Optional[str]:
    """Extrait la matière du patch/écusson."""
    try:
        if not text:
            return None
        low = text.lower()
        if "patch cuir" in low or "écusson cuir" in low:
            return "cuir"
        if "patch tissu" in low or "écusson tissu" in low:
            return "tissu"
        if "patch" in low or "écusson" in low:
            return "écusson visible"
        return None
    except Exception as exc:
        logger.debug("extract_patch_material_from_text: extraction impossible (%s)", exc)
        return None


def extract_collar_from_text(text: str) -> Optional[str]:
    """Déduit le type de col à partir du texte libre."""
    try:
        if not text:
            return None
        low = text.lower()
        collar_map = {
            "col montant": "col montant",
            "col teddy": "col teddy",
            "col officier": "col officier",
            "col chemise": "col chemise",
            "col rabattu": "col rabattu",
            "col bord": "col bord-côte",
        }
        for marker, label in collar_map.items():
            if marker in low:
                logger.debug("extract_collar_from_text: col détecté (%s)", label)
                return label
        return None
    except Exception as exc:
        logger.debug("extract_collar_from_text: extraction impossible (%s)", exc)
        return None


def extract_zip_material_from_text(text: str) -> Optional[str]:
    """Identifie la matière dominante du zip (métal/plastique)."""
    try:
        if not text:
            return None
        low = text.lower()
        if "zip métal" in low or "zip metal" in low or "fermeture métal" in low:
            return "métal"
        if "zip plastique" in low or "fermeture plastique" in low:
            return "plastique"
        return None
    except Exception as exc:
        logger.debug("extract_zip_material_from_text: extraction impossible (%s)", exc)
        return None


def extract_origin_country_from_text(text: str) -> Optional[str]:
    """Repère le pays d'origine (Made in ...) dans le texte."""
    try:
        if not text:
            return None
        low = text.lower()
        match = re.search(r"made in\s+([a-z\s]+)", low)
        if match:
            country_raw = match.group(1).strip()
            country_map = {
                "usa": "USA", "united states": "USA", "états-unis": "USA",
                "mexico": "Mexique", "mexique": "Mexique",
                "china": "Chine", "chine": "Chine",
                "bangladesh": "Bangladesh",
                "india": "Inde", "inde": "Inde",
            }
            for marker, label in country_map.items():
                if marker in country_raw:
                    return label
            return country_raw.title()
        return None
    except Exception as exc:
        logger.debug("extract_origin_country_from_text: extraction impossible (%s)", exc)
        return None


# ---------------------------------------------------------------------------
# Extraction de composition Carhartt depuis OCR structuré
# ---------------------------------------------------------------------------

def extract_carhartt_composition_from_ocr_structured(ocr_structured: dict) -> Dict[str, Optional[str]]:
    """
    Retourne un dict: exterior, body_lining, sleeve_lining, sleeve_interlining
    en se basant sur les lignes OCR retenues.
    """
    text = (ocr_structured.get("filtered_text") or "").strip()
    if not text:
        return {"exterior": None, "body_lining": None, "sleeve_lining": None, "sleeve_interlining": None}

    m = re.search(r"(?is)LIGNES RETENUES:\s*(.*)$", text)
    lines_block = m.group(1) if m else text
    s = re.sub(r"[ \t]+", " ", lines_block)
    s = s.replace("…", " ").strip()

    def pick(pattern: str) -> Optional[str]:
        mm = re.search(pattern, s, flags=re.IGNORECASE)
        return mm.group(1).strip() if mm else None

    shell = pick(r"SHELL\s*:\s*([^\.]+)")
    body = pick(r"BODY\s+LINING\s*:\s*([^\.]+)")
    sleeve = pick(r"SLEEVE\s+LINING\s*:\s*([^\.]+)")
    inter = pick(r"SLEEVE\s+INTERLINING\s*:\s*([^\.]+)")

    if not shell:
        shell = pick(r"EXT[ÉE]RIEUR\s*:\s*([^\.]+)")
    if not body:
        body = pick(r"DOUBLURE\s+DU\s+CORPS\s*:\s*([^\.]+)")
    if not sleeve:
        sleeve = pick(r"DOUBLURE\s+DE\s+LA\s+MANCHE\s*:\s*([^\.]+)")
    if not inter:
        inter = pick(r"ENTREDOUBLURE\s+DE\s+LA\s+MANCHE\s*:\s*([^\.]+)")

    def clean_percent_chunk(x: Optional[str]) -> Optional[str]:
        if not x:
            return None
        t = x
        t = re.sub(r"\s*\([^)]*\)", "", t)
        t = t.replace("REPROCESSED", "").replace("RETRANSFORMÉ", "")
        t = re.sub(r"\s+", " ", t).strip(" -:;.")
        return t.strip() or None

    return {
        "exterior": clean_percent_chunk(shell),
        "body_lining": clean_percent_chunk(body),
        "sleeve_lining": clean_percent_chunk(sleeve),
        "sleeve_interlining": clean_percent_chunk(inter),
    }


def split_carhartt_composition_blocks(text: Optional[str]) -> Dict[str, str]:
    """
    Décompose un bloc de composition en 3 segments concis :
    exterior, lining, sleeve_lining.
    """
    try:
        if not text:
            return {}
        raw = str(text).strip()
        if not raw:
            return {}

        raw = raw.replace("\r", "\n")
        chunks = []
        for part in raw.split("\n"):
            part = part.strip()
            if not part:
                continue
            chunks.extend([p.strip() for p in part.split(";") if p.strip()])

        if not chunks:
            return {}

        def _is_exterior_line(s: str) -> bool:
            low = s.lower()
            return any(k in low for k in ("exterieur", "extérieur", "exterior", "shell", "outer"))

        def _is_lining_line(s: str) -> bool:
            low = s.lower()
            return any(k in low for k in ("doublure", "interieur", "intérieur", "lining", "body lining"))

        def _is_sleeve_line(s: str) -> bool:
            low = s.lower()
            return any(k in low for k in ("manche", "manches", "sleeve"))

        def _strip_prefixes(s: str) -> str:
            return strip_leading_keyword(
                s,
                (
                    "exterieur", "extérieur", "exterior", "shell", "outer",
                    "doublure", "interieur", "intérieur", "lining", "body lining",
                    "manche", "manches", "sleeve", "sleeve lining", "doublure des manches",
                ),
            ).strip(" .:-–—")

        def _extract_percent_snippet(s: str) -> Optional[str]:
            low = s.lower()
            if "%" not in low:
                return None
            parts = [p.strip() for p in re.split(r"[,\|/]", s) if p.strip()]
            kept = [p for p in parts if "%" in p]
            if not kept:
                return _strip_prefixes(s)
            kept = [_strip_prefixes(k) for k in kept]
            kept = [k for k in kept if k]
            return ", ".join(kept) if kept else None

        def _extract_main_material(s: str) -> Optional[str]:
            snippet = _extract_percent_snippet(s)
            if snippet:
                return snippet
            cleaned = _strip_prefixes(s)
            if not cleaned:
                return None
            low = cleaned.lower()
            if any(k in low for k in ("doublure", "lining", "manche", "sleeve")):
                return None
            return cleaned

        sections = {"exterior": [], "lining": [], "sleeve_lining": []}
        current = None

        for line in chunks:
            l = line.strip()
            if not l:
                continue
            if _is_sleeve_line(l) and _is_lining_line(l):
                current = "sleeve_lining"
                sections[current].append(l)
                continue
            if _is_sleeve_line(l):
                current = "sleeve_lining"
                sections[current].append(l)
                continue
            if _is_exterior_line(l):
                current = "exterior"
                sections[current].append(l)
                continue
            if _is_lining_line(l):
                current = "lining"
                sections[current].append(l)
                continue
            if current in sections and "%" in l:
                sections[current].append(l)

        out: Dict[str, str] = {}

        for candidate in sections["exterior"]:
            v = _extract_main_material(candidate)
            if v:
                out["exterior"] = v
                break

        for candidate in sections["lining"]:
            v = _extract_percent_snippet(candidate) or _strip_prefixes(candidate)
            if v and "%" in v:
                out["lining"] = v
                break

        for candidate in sections["sleeve_lining"]:
            v = _extract_percent_snippet(candidate) or _strip_prefixes(candidate)
            if v and "%" in v:
                out["sleeve_lining"] = v
                break

        return out

    except Exception as exc:
        logger.debug("split_carhartt_composition_blocks: découpe impossible (%s)", exc)
        return {}
