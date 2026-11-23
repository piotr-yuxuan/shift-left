"""The page of sources, `docs/reference/sources.md`, checked against the citations of the skills.

The expectations come from the decision that the page lists every work that a skill or
a guide cites, and not from the page. Each guide of `programming-principles` ends with a section
"References", whose links are its sources; the page has one row per guide, whose first link leads
to the guide and whose other links are exactly the guide's, so that a source dropped from a guide
leaves the page too. `karpathy-guidelines` links its author's post in its first line, and its
`NOTICE.md` names the repository and the commit that it was copied from; both addresses and the
commit appear in the page.
`concept-design` ends with a line "Sources" that names its works, each title in quotes or in
italics; each title appears in the page. The page links files of this repository by relative
paths, from its own directory, and each such link leads to a file that exists, so that a rename
leaves no link that leads nowhere.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE_PATH = ROOT / "docs/reference/sources.md"
PAGE = PAGE_PATH.read_text(encoding="utf-8")
SKILLS = ROOT / "plugins/principles/skills"
GUIDES = SKILLS / "programming-principles/references"
LINK = re.compile(r"\]\(([^)\s]+)\)")
URL = re.compile(r"https?://[^\s)>]+")


class Sources(unittest.TestCase):
    def test_each_guide_has_one_row_with_exactly_its_references(self):
        rows = {}
        for line in PAGE.splitlines():
            links = LINK.findall(line) if line.startswith("|") else []
            if links and not URL.match(links[0]):
                rows.setdefault((PAGE_PATH.parent / links[0]).resolve(), []).append(links[1:])
        guides = sorted(GUIDES.glob("*.md"))
        self.assertTrue(guides, "no guide found")
        for guide in guides:
            references = guide.read_text(encoding="utf-8").split("## References", 1)
            with self.subTest(guide=guide.name):
                self.assertEqual(len(references), 2, "no section References")
                cited = LINK.findall(references[1])
                self.assertTrue(cited, "no link under References")
                self.assertEqual(rows.get(guide.resolve()), [cited], "not one row of the guide's links")

    def test_the_page_holds_the_origins_of_the_karpathy_guidelines(self):
        skill = (SKILLS / "karpathy-guidelines/SKILL.md").read_text(encoding="utf-8")
        notice = (SKILLS / "karpathy-guidelines/NOTICE.md").read_text(encoding="utf-8")
        body = skill.split("---", 2)[2]
        first = next(line for line in body.splitlines() if line and not line.startswith("#"))
        commits = re.findall(r"\b[0-9a-f]{40}\b", notice)
        self.assertTrue(commits, "no commit in NOTICE.md")
        for commit in commits:
            self.assertIn(commit, PAGE)
        for name, text in (("SKILL.md", first), ("NOTICE.md", notice)):
            urls = URL.findall(text)
            with self.subTest(file=name):
                self.assertTrue(urls, "no address found")
                for url in urls:
                    self.assertIn(url, PAGE)

    def test_the_page_names_every_source_of_concept_design(self):
        skill = (SKILLS / "concept-design/SKILL.md").read_text(encoding="utf-8")
        line = " ".join(skill.split("Sources:", 1)[1].split())
        titles = re.findall(r'"([^"]+)"|\*([^*]+)\*', line)
        self.assertTrue(titles, "no title in the line Sources")
        for quoted, emphasised in titles:
            with self.subTest(title=quoted or emphasised):
                self.assertIn(quoted or emphasised, PAGE)

    def test_each_relative_link_of_the_page_leads_to_a_file(self):
        for link in LINK.findall(PAGE):
            if URL.match(link):
                continue
            with self.subTest(link=link):
                self.assertTrue((PAGE_PATH.parent / link.split("#", 1)[0]).resolve().is_file())


if __name__ == "__main__":
    unittest.main()
