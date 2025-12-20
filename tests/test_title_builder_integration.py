import unittest

from domain.title_builder import (
    build_jacket_carhart_title,
    build_jean_levis_title,
    build_pull_tommy_title,
)


class TitleBuilderIntegrationTestCase(unittest.TestCase):
    def test_build_jean_levis_title_with_engine(self) -> None:
        features = {
            "brand": "Levi's",
            "model": "511",
            "size_fr": "38",
            "size_us": "28",
            "fit": "skinny",
            "cotton_percent": 98,
            "elasthane_percent": 2.5,
            "gender": "femme",
            "color": "bleu, noir",
            "sku": "ABC123",
        }

        title = build_jean_levis_title(features)

        self.assertEqual(
            title,
            "Jean Levi's 511 FR38 W28 coupe Skinny stretch 98% coton bleu noir femme - ABC123",
        )

    def test_build_pull_tommy_title_with_pima_and_specificity(self) -> None:
        features = {
            "brand": "Tommy Hilfiger",
            "garment_type": "pull",
            "gender": "femme",
            "size": "M",
            "neckline": "V",
            "pattern": "torsade",
            "material": "coton",
            "cotton_percent": 90,
            "main_colors": ["bleu", "rouge", "vert"],
            "sku": "PTF123",
            "sku_status": "ok",
            "is_pima": True,
            "specificity": "oversize",
        }

        title = build_pull_tommy_title(features)

        self.assertEqual(
            title,
            "Pull Tommy Hilfiger Premium Torsade taille M bleu rouge 90% coton col V femme oversize - PTF123",
        )

    def test_build_jacket_carhart_title_with_specificities(self) -> None:
        features = {
            "brand": "Carhartt",
            "model": "Detroit Jacket",
            "size": "M",
            "color": "marron",
            "gender": "homme",
            "has_hood": False,
            "is_camouflage": False,
            "is_realtree": False,
            "pattern": "",
            "collar": "col chemise",
            "lining": "doublure sherpa",
            "closure": "zip",
            "exterior": "100% coton",
            "sku": "JCR001",
            "sku_status": "ok",
        }

        title = build_jacket_carhart_title(features)

        self.assertEqual(
            title,
            "Jacket Carhartt Detroit taille M col chemise doublure sherpa zip 100% coton marron homme - JCR001",
        )
        self.assertEqual(title.count("Jacket"), 1)
        self.assertNotIn("Veste", title)

    def test_build_jacket_carhart_title_sanitizes_size_and_keeps_gender_material(self) -> None:
        features = {
            "brand": "Carhartt",
            "model": "Active Jacket",
            "size": "M JCR1",
            "color": "noir, gris",
            "gender": "homme",
            "has_hood": True,
            "is_camouflage": False,
            "is_realtree": False,
            "pattern": "",
            "collar": "",
            "lining": "doublure matelassée",
            "closure": "zip",
            "exterior": "100% coton",
            "sku": "JCR001",
            "sku_status": "ok",
        }

        title = build_jacket_carhart_title(features)

        self.assertIn("Jacket à capuche Carhartt Active taille M", title)
        self.assertIn("100% coton", title)
        self.assertIn("homme", title)
        self.assertIn("- JCR001", title)
        self.assertNotIn("JCR1", title.split("taille")[1].split("-")[0])


if __name__ == "__main__":
    unittest.main()
