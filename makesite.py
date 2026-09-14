"""Build an Obsidian-authored blog. Only explicitly published notes are emitted."""

import datetime as dt
import logging
import re
import shutil
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown.extensions import Extension
from markdown.extensions.toc import slugify as heading_slugify
from markdown.inlinepatterns import InlineProcessor
from markdown.treeprocessors import Treeprocessor
from slugify import slugify


def parse_bool(value, default=False):
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized not in {"true", "yes", "1", "false", "no", "0"}:
        raise ValueError(f"Expected a boolean, got {value!r}")
    return normalized in {"true", "yes", "1"}


class SiteGenerator:
    def __init__(self, content_dir, publish_dir, static_dir, layout_dir):
        self.content_dir = Path(content_dir).resolve()
        self.base_dir = self.content_dir.parent
        self.publish_dir = Path(publish_dir).resolve()
        self.static_dir = Path(static_dir).resolve()
        self.template_env = Environment(
            loader=FileSystemLoader(layout_dir), autoescape=select_autoescape(["html"])
        )
        self.timezone = ZoneInfo("Asia/Dhaka")
        self.site_params = {
            "tld": "reveille.xyz", "author": "Sakib Hasan",
            "site_url": "https://reveille.xyz", "static_dir": self.static_dir.name,
            "now": dt.datetime.now(self.timezone),
        }
        self.notes = {}

    def _extract_headers(self, text):
        lines = text.lstrip("\ufeff").splitlines()
        if lines and lines[0].strip() == "---":
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            if end is None:
                raise ValueError("Unclosed YAML properties block")
            headers = yaml.safe_load("\n".join(lines[1:end])) or {}
            if not isinstance(headers, dict):
                raise ValueError("Properties must be a YAML mapping")
            return headers, "\n".join(lines[end + 1:])
        headers = {}
        consumed = 0
        for line in lines:
            match = re.fullmatch(r"\s*<!--\s*([^:]+):\s*(.*?)\s*-->\s*", line)
            if not match:
                break
            headers[match[1].strip()] = match[2]
            consumed += 1
        return headers, "\n".join(lines[consumed:])

    def fread(self, filepath):
        try:
            headers, body = self._extract_headers(filepath.read_text(encoding="utf-8"))
            draft = parse_bool(headers.get("draft"), default=True)
            if draft:
                return {"draft": True, "source": filepath}
            title = str(headers.get("title") or "").strip()
            if not title:
                raise ValueError("Published notes need a nonempty title")
            slug = str(headers.get("slug") or slugify(filepath.stem)).strip()
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
                raise ValueError("Slug must contain lowercase letters, numbers and single hyphens")
            fixed = parse_bool(headers.get("fixed_page"))
            published = None
            if not fixed:
                date = dt.date.fromisoformat(str(headers["date"]))
                time = dt.datetime.strptime(str(headers.get("time", "00:00")), "%H:%M").time()
                published = dt.datetime.combine(date, time, self.timezone)
            url = f"/{slug}/" if fixed else f"/blog/{slug}/"
            if url in {"/all/", "/blog/", "/static/"}:
                raise ValueError(f"Reserved URL: {url}")
            return {**headers, "title": title, "slug": slug, "draft": False,
                    "fixed_page": fixed, "published": published,
                    "date": published.date() if published else None,
                    "body": body, "source": filepath, "url": url,
                    "canonical_url": self.site_params["site_url"] + url}
        except (ValueError, KeyError, yaml.YAMLError) as exc:
            raise ValueError(f"{filepath}: {exc}") from exc

    def resolve_link(self, value, source, image=False, wiki=False):
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return value
        if not parsed.path:
            return "#" + heading_slugify(unquote(parsed.fragment), "-") if wiki and parsed.fragment else value
        path = unquote(parsed.path)
        if path.startswith("/") and not image and not path.endswith(".md"):
            return value
        candidates = [source.parent / path, self.base_dir / path, self.content_dir / path]
        if not Path(path).suffix and not image:
            candidates = [p.with_suffix(".md") for p in candidates]
        if path.startswith("/"):
            candidates = [self.base_dir / path.lstrip("/")]
        target = next((p.resolve() for p in candidates if p.is_file()), None)
        if target is None and wiki:
            roots = [self.content_dir, self.static_dir]
            name = Path(path).name
            if not Path(path).suffix and not image:
                name += ".md"
            matches = [p.resolve() for root in roots for p in root.rglob(name) if p.is_file()]
            if len(matches) == 1:
                target = matches[0]
            elif len(matches) > 1:
                raise ValueError(f"{source}: ambiguous link {value!r}; use its folder path")
        if target in self.notes:
            note = self.notes[target]
            if image:
                raise ValueError(f"{source}: note embeds are unsupported; link to {value!r} instead")
            if note["draft"]:
                raise ValueError(f"{source}: link to unpublished draft {value!r}")
            result = note["url"]
        elif target and target.is_relative_to(self.static_dir):
            result = "/" + quote(target.relative_to(self.base_dir).as_posix())
        else:
            raise ValueError(f"{source}: missing or unsupported local link {value!r}")
        if parsed.query:
            result += "?" + parsed.query
        if parsed.fragment:
            fragment = unquote(parsed.fragment)
            result += "#" + quote(heading_slugify(fragment, "-") if wiki else fragment)
        return result

    def render_markdown(self, body, source, absolute=False):
        generator = self

        class WikiLinks(InlineProcessor):
            def handleMatch(self, match, data):
                embed, target, alias = match.group(1), match.group(2), match.group(3)
                element = ET.Element("img" if embed else "a")
                url = generator.resolve_link(target, source, image=bool(embed), wiki=True)
                element.set("src" if embed else "href", url)
                if embed:
                    element.set("alt", alias or Path(target).stem)
                else:
                    element.text = alias or target
                element.set("data-wiki-resolved", "true")
                return element, match.start(0), match.end(0)

        class LocalLinks(Treeprocessor):
            def run(self, root):
                for element in root.iter():
                    if element.tag not in {"a", "img"}:
                        continue
                    key = "src" if element.tag == "img" else "href"
                    value = element.get(key, "")
                    if not element.attrib.pop("data-wiki-resolved", None):
                        value = generator.resolve_link(value, source, image=element.tag == "img")
                    if absolute and value.startswith("/"):
                        value = generator.site_params["site_url"] + value
                    element.set(key, value)
                    if element.tag == "img":
                        element.set("loading", "lazy")

        class ObsidianMarkdown(Extension):
            def extendMarkdown(self, md):
                md.inlinePatterns.register(WikiLinks(r"(!?)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", md), "wikilinks", 175)
                md.treeprocessors.register(LocalLinks(md), "local_links", 15)

        return markdown.markdown(body, extensions=["fenced_code", "tables", "footnotes", "toc", ObsidianMarkdown()])

    def fwrite(self, relative_path, content):
        full_path = self.publish_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def generate_feed(self, posts):
        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")
        for key, value in {"title": "Reveille — Sakib Hasan", "link": self.site_params["site_url"],
                           "description": "Personal writings by Sakib Hasan", "language": "en"}.items():
            ET.SubElement(channel, key).text = value
        for post in posts[:20]:
            item = ET.SubElement(channel, "item")
            for key, value in {"title": post["title"], "link": post["canonical_url"],
                               "pubDate": format_datetime(post["published"]),
                               "description": self.render_markdown(post["body"], post["source"], absolute=True)}.items():
                ET.SubElement(item, key).text = value
            ET.SubElement(item, "guid", isPermaLink="true").text = post["canonical_url"]
        return ET.tostring(rss, encoding="unicode", xml_declaration=True)

    def build(self):
        # Validate and render before touching the previous output.
        for asset in self.static_dir.rglob("*"):
            if asset.is_file() and asset.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                if asset.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError(f"{asset}: image exceeds 2 MiB; resize/compress before committing (see README)")
        self.notes = {path: self.fread(path) for path in sorted(self.content_dir.rglob("*.md"))}
        outputs = {}
        posts = []
        for note in self.notes.values():
            if note["draft"]:
                continue
            dest = note["url"].lstrip("/") + "index.html"
            if dest in outputs:
                raise ValueError(f"Duplicate URL: {note['url']}")
            content = self.render_markdown(note["body"], note["source"])
            outputs[dest] = self.template_env.get_template("post.html").render(
                **{**self.site_params, **note, "content": content})
            if not note["fixed_page"]:
                posts.append(note)
        posts.sort(key=lambda p: p["published"], reverse=True)
        for dest, template, items, url in [("index.html", "home.html", posts[:10], "/"),
                                            ("all/index.html", "all.html", posts, "/all/")]:
            outputs[dest] = self.template_env.get_template(template).render(
                **self.site_params, posts=items, canonical_url=self.site_params["site_url"] + url)
        outputs["404.html"] = self.template_env.get_template("post.html").render(
            **self.site_params, title="404 — Page not found", fixed_page=True,
            content="The page you are looking for does not exist.")
        outputs["feed.xml"] = self.generate_feed(posts)
        if self.publish_dir != self.base_dir / "_site":
            raise ValueError("Publish directory must be the project's _site directory")
        if self.publish_dir.exists():
            shutil.rmtree(self.publish_dir)
        self.publish_dir.mkdir(parents=True)
        shutil.copytree(self.static_dir, self.publish_dir / self.static_dir.name)
        for path, content in outputs.items():
            self.fwrite(path, content)
        logging.info("Built %d posts and %d output files", len(posts), len(outputs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    SiteGenerator("content", "_site", "static", "layout").build()
