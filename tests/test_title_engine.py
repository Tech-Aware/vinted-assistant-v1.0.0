import unittest

from domain.title_engine import (
    JeanSpec,
    TitleBlock,
    TitleRules,
    render_title,
)


class TitleEngineTestCase(unittest.TestCase):
    def test_order_and_capitalization_before_and_after_size(self) -> None:
        spec = JeanSpec()
        blocks = [
            TitleBlock(kind="brand", value="levi's", capitalize=None, trim_priority=1, critical=True),
            TitleBlock(kind="category", value="jean", capitalize=True, trim_priority=1, critical=True),
            TitleBlock(kind="size", value="fr38", capitalize=False, trim_priority=1, critical=True),
            TitleBlock(kind="fit", value="skinny", capitalize=None, trim_priority=1, critical=False),
            TitleBlock(kind="color_primary", value="bleu", trim_priority=1, critical=False),
        ]

        title = render_title(blocks, spec, TitleRules(max_length=100))
        self.assertEqual(title, "Jean Levi's fr38 skinny bleu")

    def test_color_limiting_applies_max_two(self) -> None:
        spec = JeanSpec()
        blocks = [
            TitleBlock(kind="category", value="Jean", critical=True),
            TitleBlock(kind="brand", value="Levi's", critical=True),
            TitleBlock(kind="color_primary", value="bleu"),
            TitleBlock(kind="color_secondary", value="noir"),
            TitleBlock(kind="color_secondary", value="rouge"),
        ]

        title = render_title(blocks, spec, TitleRules(max_length=100, max_colors=2))
        lowered = title.lower()
        self.assertNotIn("rouge", lowered)
        self.assertEqual(lowered.count("bleu"), 1)
        self.assertEqual(lowered.count("noir"), 1)

    def test_trimming_respects_priority(self) -> None:
        spec = JeanSpec()
        rules = TitleRules(max_length=25)
        blocks = [
            TitleBlock(kind="category", value="Jean", critical=True, trim_priority=1),
            TitleBlock(kind="brand", value="Levi's", critical=True, trim_priority=1),
            TitleBlock(kind="model", value="511", trim_priority=1),
            TitleBlock(kind="color_primary", value="bleu", trim_priority=2),
            TitleBlock(kind="color_secondary", value="gris", trim_priority=3),
            TitleBlock(kind="sku", value="- ABC123", trim_priority=4),
        ]

        title = render_title(blocks, spec, rules)
        self.assertLessEqual(len(title), rules.max_length)
        # Le bloc de trim_priority le plus élevé est supprimé en premier
        self.assertNotIn("ABC123", title)


if __name__ == "__main__":
    unittest.main()
