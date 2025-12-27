import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from domain.ocr_structurer import StructuredOCRExtractor


def test_composition_size_origin_and_sku():
    raw = """
    100% cotton
    Taille : M
    Made in Mexico
    RN 12345
    """
    extractor = StructuredOCRExtractor()
    structured = extractor.structure(raw)

    assert structured.size_candidates == ["M"]
    assert structured.origin == "Made in Mexico"
    assert any(item.material == "coton" and item.percent == 100 for item in structured.composition_items)
    assert "RN12345" in structured.sku_candidates
    assert "[OCR_CADRÉ]" in structured.filtered_text


def test_multiple_compositions_and_sizes():
    raw = """
    COTON 80% / POLYESTER 20%
    EU 42
    W32 L34
    """
    structured = StructuredOCRExtractor().structure(raw)

    assert any(item.material == "coton" and item.percent == 80 for item in structured.composition_items)
    assert any(item.material == "polyester" and item.percent == 20 for item in structured.composition_items)
    assert "EU42" in [s.replace(" ", "") for s in structured.size_candidates]
    assert any("W32" in size and "34" in size for size in structured.size_candidates)


def test_material_before_percent():
    raw = """
    POLYAMIDE 12% ELASTHANNE 3%
    MadeIn Italy
    """
    structured = StructuredOCRExtractor().structure(raw)

    assert any(item.material == "polyamide" and item.percent == 12 for item in structured.composition_items)
    assert any(item.material == "élasthanne" and item.percent == 3 for item in structured.composition_items)
    assert structured.origin == "Made in Italy"


def test_generic_sku_patterns():
    raw = """
    STYLE: EJ001
    REF 9ZK21
    CA1234
    """
    structured = StructuredOCRExtractor().structure(raw)

    assert "EJ001" in structured.sku_candidates
    assert "REF9ZK21" in structured.sku_candidates
    assert "CA1234" in structured.sku_candidates


def test_internal_sku_with_separator():
    raw = """
    PTF 217
    TAILLE M
    """
    structured = StructuredOCRExtractor().structure(raw)

    assert "PTF217" in structured.sku_candidates


def test_no_information_returns_empty_structures():
    raw = """
    Lorem ipsum dolor sit amet
    Ceci est une ligne sans donnée utile
    """
    structured = StructuredOCRExtractor().structure(raw)

    assert structured.size_candidates == []
    assert structured.composition_items == []
    assert structured.origin is None
    assert structured.sku_candidates == []
    assert "- (none)" in structured.filtered_text
