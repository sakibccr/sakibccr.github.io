import shutil
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

from makesite import SiteGenerator
from scripts.import_image import import_image


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "content/blog").mkdir(parents=True)
        (self.root / "static/assets/images").mkdir(parents=True)
        shutil.copytree(Path(__file__).resolve().parents[1] / "layout", self.root / "layout")
        self.site = SiteGenerator(self.root / "content", self.root / "_site",
                                  self.root / "static", self.root / "layout")

    def note(self, name="post", properties=None, body="Hello"):
        properties = properties if properties is not None else (
            'title: A post\ndate: 2026-01-19\ntime: "17:13"\ndraft: false')
        path = self.root / "content/blog" / f"{name}.md"
        path.write_text(f"---\n{properties}\n---\n{body}", encoding="utf-8")
        return path

    def output(self, name="post"):
        return (self.root / f"_site/blog/{name}/index.html").read_text()

    def test_missing_draft_flag_and_unfinished_drafts_are_not_published(self):
        self.note("private", "title: Private")
        self.note("unfinished", "draft: true", "![[missing.png]]")
        self.site.build()
        self.assertFalse((self.root / "_site/blog").exists())
        self.assertEqual(ET.parse(self.root / "_site/feed.xml").findall("channel/item"), [])

    def test_invalid_published_metadata_fails_with_filename(self):
        for props in ["draft: false", "draft: maybe", "title: Test\ndraft: false\ndate: wrong",
                      "title: Test\ndraft: false\ndate: 2026-01-19\nslug: ../escape"]:
            with self.subTest(props=props):
                self.note(properties=props)
                with self.assertRaisesRegex(ValueError, "post.md"):
                    self.site.build()

    def test_title_and_date_changes_keep_explicit_slug(self):
        path = self.note(properties='title: First\ndate: 2026-01-19\nslug: stable\ndraft: false')
        self.site.build()
        path.write_text(path.read_text().replace("First", "Second").replace("2026-01-19", "2026-02-20"))
        self.site.build()
        self.assertIn("Second", self.output("stable"))
        self.assertIn('href="https://reveille.xyz/blog/stable/"', self.output("stable"))

    def test_filename_fallback_does_not_depend_on_title(self):
        self.note("file-name")
        self.site.build()
        self.assertIn("A post", self.output("file-name"))

    def test_duplicate_and_reserved_routes_fail(self):
        self.note("first", "title: First\nfixed_page: true\nslug: all\ndraft: false")
        with self.assertRaisesRegex(ValueError, "Reserved"):
            self.site.build()
        props = "title: Same\ndate: 2026-01-19\nslug: same\ndraft: false"
        self.note("first", props)
        self.note("second", props)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.site.build()

    def test_wiki_and_markdown_links_images_and_code(self):
        self.note("other")
        image = self.root / "static/assets/images/a photo.png"
        Image.new("RGB", (10, 10)).save(image)
        self.note(body='[[other|Read more]]\n\n[Other](other.md)\n\n'
                       '![[a photo.png]]\n\n![Alt](../../static/assets/images/a%20photo.png)\n\n'
                       '`[[not-a-link]]`\n\n```\n![[not-an-image]]\n```')
        self.site.build()
        html = self.output()
        self.assertEqual(html.count('href="/blog/other/"'), 2)
        self.assertEqual(html.count('src="/static/assets/images/a%20photo.png"'), 2)
        self.assertIn("<code>[[not-a-link]]</code>", html)
        self.assertIn("![[not-an-image]]", html)

    def test_draft_links_and_missing_images_fail(self):
        self.note("private", "draft: true")
        for body in ["[[private]]", "![Missing](missing.jpg)", "![[private]]"]:
            with self.subTest(body=body):
                self.note(body=body)
                with self.assertRaises(ValueError):
                    self.site.build()

    def test_feed_escapes_titles_and_uses_absolute_links_and_dhaka_time(self):
        self.note("other")
        self.note(properties='title: "Cats & <dogs>"\ndate: 2026-01-19\ntime: "23:30"\ndraft: false',
                  body="[[other]]")
        self.site.build()
        items = ET.parse(self.root / "_site/feed.xml").findall("channel/item")
        self.assertEqual(items[0].findtext("title"), "Cats & <dogs>")
        self.assertIn("+0600", items[0].findtext("pubDate"))
        self.assertIn('href="https://reveille.xyz/blog/other/"', items[0].findtext("description"))
        self.assertIn("Cats &amp; &lt;dogs&gt;", self.output())

    def test_invalid_build_preserves_previous_site(self):
        self.note()
        self.site.build()
        previous = self.output()
        self.note(body="![[missing.png]]")
        with self.assertRaises(ValueError):
            self.site.build()
        self.assertEqual(self.output(), previous)

    def test_legacy_comment_headers(self):
        path = self.root / "content/blog/legacy.md"
        path.write_text('<!-- title: Legacy -->\n<!-- date: 2026-01-19 -->\n'
                        '<!-- time: 17:13 -->\n<!-- draft: no -->\nBody')
        self.site.build()
        self.assertIn("Legacy", self.output("legacy"))

    def test_wiki_heading_links_match_generated_ids(self):
        self.note("other", body="## A heading")
        self.note(body="[[other#A heading]]\n\n[[#Local heading]]\n\n## Local heading")
        self.site.build()
        self.assertIn('href="/blog/other/#a-heading"', self.output())
        self.assertIn('href="#local-heading"', self.output())
        self.assertIn('id="a-heading"', self.output("other"))

    def test_oversized_images_fail_build(self):
        asset = self.root / "static/assets/images/large.jpg"
        asset.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "exceeds 2 MiB"):
            self.site.build()

    def test_image_import_preserves_original_and_refuses_overwrite(self):
        source = self.root / "original.jpg"
        exif = Image.Exif()
        exif[270] = "private metadata"
        Image.new("RGB", (2400, 1200), "red").save(source, exif=exif)
        original = source.read_bytes()
        dest = self.root / "static/assets/images/photo.webp"
        import_image(source, dest)
        with Image.open(dest) as result:
            self.assertEqual(result.size, (1600, 800))
            self.assertFalse(result.getexif())
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            import_image(source, dest)


if __name__ == "__main__":
    unittest.main()
