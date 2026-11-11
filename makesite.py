from __future__ import annotations

import datetime as dt
import email.utils
import logging
import re
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from slugify import slugify

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(
    r"\A\+\+\+[ \t]*\r?\n(.*?)\r?\n\+\+\+[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)


def to_rfc822(val: dt.datetime | None) -> str:
    """Format datetime according to RFC 822 for RSS feeds."""
    if not val:
        return ""
    if isinstance(val, dt.date) and not isinstance(val, dt.datetime):
        val = dt.datetime.combine(val, dt.time.min)
    if val.tzinfo is None:
        val = val.replace(tzinfo=dt.UTC)
    return email.utils.format_datetime(val)


@dataclass(frozen=True)
class Page:
    """Represents a parsed content page or blog post."""

    source: Path
    title: str
    slug: str
    content: str
    datetime: dt.datetime | None
    fixed_page: bool = False
    draft: bool = False
    metadata: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def destination(self) -> Path:
        """Calculate relative file destination path."""
        if self.fixed_page:
            return Path(self.slug) / "index.html"
        if not self.datetime:
            raise ValueError(
                f"Post {self.source} requires a datetime to compute destination"
            )
        return Path(
            self.source.parent.name,
            f"{self.datetime.strftime('%Y-%m-%d')}-{self.slug}",
            "index.html",
        )

    @property
    def url(self) -> str:
        """Calculate canonical relative URL."""
        return f"/{self.destination.parent.as_posix()}/"

    def __getitem__(self, key: str) -> Any:
        """Allow backwards-compatible dict-style access in Jinja templates."""
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata[key]

    def to_context(self) -> dict[str, Any]:
        """Export page attributes as flat template context."""
        return {
            **self.metadata,
            "title": self.title,
            "slug": self.slug,
            "content": self.content,
            "datetime": self.datetime,
            "fixed_page": self.fixed_page,
            "draft": self.draft,
            "url": self.url,
            "page": self,
        }

    @classmethod
    def from_file(cls, filepath: Path, md: markdown.Markdown) -> Page:
        """Parse frontmatter and compile Markdown into a Page instance."""
        text = filepath.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        meta, body = (
            (tomllib.loads(match.group(1)), text[match.end() :])
            if match
            else ({}, text)
        )

        is_page = bool(meta.get("fixed_page", False))
        is_draft = bool(meta.get("draft", False))
        parsed_dt = meta.get("datetime")

        if not is_page and not is_draft and not parsed_dt:
            raise ValueError(f"Missing required metadata 'datetime' in {filepath}")

        # Normalize date-only TOML literals to full datetimes
        if isinstance(parsed_dt, dt.date) and not isinstance(parsed_dt, dt.datetime):
            parsed_dt = dt.datetime.combine(parsed_dt, dt.time.min)

        md.reset()
        title = meta.get("title", filepath.stem)
        slug = slugify(meta.get("slug") or title) or filepath.stem

        return cls(
            source=filepath,
            title=title,
            slug=slug,
            content=md.convert(body),
            datetime=parsed_dt,
            fixed_page=is_page,
            draft=is_draft,
            metadata=meta,
        )


class SiteBuilder:
    def __init__(
        self,
        content_dir: str,
        publish_dir: str,
        static_dir: str,
        layout_dir: str,
        config_filename: str = "config.toml",
    ):
        self.base_dir = Path(__file__).resolve().parent
        self.content_dir = (self.base_dir / content_dir).resolve()
        self.publish_dir = (self.base_dir / publish_dir).resolve()
        self.static_dir = (self.base_dir / static_dir).resolve()
        self.layout_dir = (self.base_dir / layout_dir).resolve()

        # Load configuration from TOML file if it exists
        config_path = self.base_dir / config_filename
        file_config: dict[str, Any] = {}
        if config_path.is_file():
            logger.info("Loading configuration from %s", config_path)
            with open(config_path, "rb") as f:
                file_config = tomllib.load(f)
        else:
            logger.warning(
                "Config file not found at %s. Using default settings.", config_path
            )

        self.build_time = dt.datetime.now(dt.UTC)

        # Combine loaded config with dynamic runtime fields
        self.site_config: dict[str, Any] = {
            "tld": "reveille.xyz",
            "author": "Sakib Hasan",
            "site_url": "https://reveille.xyz",
            **file_config,  # Values from config.toml override defaults above
            "build_time": self.build_time,
            "now": self.build_time,  # Required by base.html footer
            "static_dir": self.static_dir.name,
        }

        self.env = Environment(
            loader=FileSystemLoader(self.layout_dir),
            autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml")),
        )
        self.env.filters["rfc822_date"] = to_rfc822
        self.env.globals.update(self.site_config)

        self.md = markdown.Markdown(
            extensions=["extra", "codehilite", "toc", "sane_lists"]
        )

    def clean_output_directory(self) -> None:
        """Prepare publish directory while preventing accidental source deletion."""
        for path in (self.base_dir, self.content_dir, self.static_dir, self.layout_dir):
            if self.publish_dir == path or path.is_relative_to(self.publish_dir):
                raise ValueError(
                    f"Publish directory cannot enclose source path: {path}"
                )

        if not self.static_dir.is_dir():
            raise FileNotFoundError(f"Static directory not found: {self.static_dir}")

        if self.publish_dir.exists():
            shutil.rmtree(self.publish_dir)
        self.publish_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            self.static_dir, self.publish_dir / self.static_dir.name, dirs_exist_ok=True
        )

    def render_to_file(
        self, template_name: str, rel_dest: str | Path, **context: Any
    ) -> None:
        """Render a Jinja template and write it to the publication directory."""
        dest = (self.publish_dir / rel_dest).resolve()
        if not dest.is_relative_to(self.publish_dir):
            raise ValueError(f"Path traversal detected: {rel_dest}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        rendered = self.env.get_template(template_name).render(**context)
        dest.write_text(rendered, encoding="utf-8")
        logger.info("Generated %s", dest)

    def build_pages(self) -> list[Page]:
        """Process all Markdown files, write individual pages, and return published posts."""
        posts: list[Page] = []
        seen_destinations: set[Path] = set()

        for filepath in sorted(self.content_dir.rglob("*.md")):
            logger.info("Processing %s", filepath)
            page = Page.from_file(filepath, self.md)

            if page.draft:
                logger.info("Skipping draft: %s", filepath)
                continue

            dest = page.destination
            if dest in seen_destinations:
                raise ValueError(f"Duplicate route detected: {dest}")
            seen_destinations.add(dest)

            self.render_to_file("post.html", dest, **page.to_context())

            if not page.fixed_page:
                posts.append(page)

        return sorted(posts, key=lambda p: p.datetime, reverse=True)

    def build(self) -> None:
        """Run the full site build pipeline."""
        logger.info("Starting site build")
        self.clean_output_directory()
        posts = self.build_pages()

        # Render listings, feed, and error pages
        self.render_to_file("home.html", "index.html", posts=posts[:10])
        self.render_to_file("all.html", "all/index.html", posts=posts)
        self.render_to_file("feed.xml", "feed.xml", posts=posts[:20])
        self.render_to_file(
            "post.html",
            "404.html",
            title="404 - Page Not Found",
            content="<p>The page you are looking for does not exist.</p>",
            fixed_page=True,
            draft=False,
            datetime=None,
        )
        logger.info("Build completed successfully. Published %d posts.", len(posts))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    SiteBuilder("content", "_site", "static", "layout").build()
