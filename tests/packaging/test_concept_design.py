"""The skill `concept-design` of `principles`, checked against the paper that it follows.

The expectations come from Daniel Jackson, "Concept Design Moves", NASA Formal Methods 2022,
LNCS 13260, section 3, and not from the skill: six moves in three pairs of duals, each move
favouring one quality at the cost of another and its dual the reverse. Split gains flexibility at
the cost of simplicity, Merge the reverse; Unify gains generality at the cost of specificity,
Specialize the reverse; Tighten gains automation at the cost of control, Loosen the reverse.

The skill holds them as a table of four columns: the move, what it does, what it gains and what it
costs. Each of the six moves has one row, whose Gains begins with the quality that the move gains
and whose Costs with the one that it gives up, read ignoring case. The decisions of plan 027 add
that the skill says no move is right in itself, that the moves are not a procedure, and that a move
for a use still to come is what YAGNI rules out; that it names the paper as its source; and that it
has at most 120 lines, so that the skill stays a vocabulary and not a method.
"""

import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "plugins/principles/skills/concept-design/SKILL.md"
TEXT = SKILL.read_text(encoding="utf-8")
QUALITIES = {
    "Split": ("flexibility", "simplicity"),
    "Merge": ("simplicity", "flexibility"),
    "Unify": ("generality", "specificity"),
    "Specialize": ("specificity", "generality"),
    "Tighten": ("automation", "control"),
    "Loosen": ("control", "automation"),
}


class ConceptDesign(unittest.TestCase):
    def test_each_move_gains_and_costs_the_qualities_of_the_paper(self):
        rows = {}
        for line in TEXT.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] in QUALITIES:
                rows.setdefault(cells[0], []).append(cells)
        for move, (gain, cost) in QUALITIES.items():
            with self.subTest(move=move):
                self.assertEqual(len(rows.get(move, [])), 1, "not one row of the table")
                _, _, gains, costs = rows[move][0]
                self.assertTrue(gains.lower().startswith(gain), f"gains {gains!r}")
                self.assertTrue(costs.lower().startswith(cost), f"costs {costs!r}")

    def test_the_skill_holds_its_guards_and_names_its_source(self):
        text = " ".join(TEXT.split())
        for phrase in (
            "no move is right in itself",
            "not a procedure",
            "YAGNI",
            "Concept Design Moves",
            "NASA Formal Methods 2022",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_skill_keeps_within_its_length(self):
        self.assertLessEqual(len(TEXT.splitlines()), 120)


if __name__ == "__main__":
    unittest.main()
