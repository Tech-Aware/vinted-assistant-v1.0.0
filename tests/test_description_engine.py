import unittest

from domain.description_engine import DescriptionBlockOrder, render_description


class DescriptionEngineTestCase(unittest.TestCase):
    def test_render_description_keeps_placeholder(self) -> None:
        blocks = DescriptionBlockOrder(
            title_line="Jean Levi's 501 pour femme.",
            commercial_paragraph="Taille W28 (FR38), coupe Skinny.",
            composition_line="Composition non lisible (voir étiquettes en photo).",
            state_logistics_lines=["Très bon état.", "📏 Mesures détaillées visibles en photo pour plus de précisions."],
            footer_lines=["📦 Envoi rapide et soigné.", "✨ Retrouvez tous mes articles Levi’s ici 👉 #durin31fr38"],
            hashtags_line="#jeanlevis",
        )

        description = render_description(blocks)

        self.assertIn("Composition non lisible (voir étiquettes en photo).", description)
        self.assertTrue(description.strip().endswith("#jeanlevis"))

    def test_render_description_orders_blocks(self) -> None:
        blocks = DescriptionBlockOrder(
            title_line="Pull Tommy Hilfiger",
            commercial_paragraph="Maille douce.",
            composition_line="Composition : 90% coton.",
            state_logistics_lines=["Très bon état."],
            footer_lines=["Footer ligne 1", "Footer ligne 2"],
            hashtags_line="#tommyhilfiger",
        )

        description = render_description(blocks).splitlines()
        self.assertEqual(description[0], "Pull Tommy Hilfiger")
        self.assertIn("Footer ligne 1", "\n".join(description))


if __name__ == "__main__":
    unittest.main()
