import shutil
import logging
import datetime
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader
from slugify import slugify


LOG_FORMAT = "[%(levelname)s] %(message)s"


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "yes", "1"}


class SiteGenerator:
    def __init__(self, content_dir, publish_dir, static_dir, layout_dir):
        self.base_dir = Path(__file__).resolve().parent
        self.content_dir = Path(content_dir)
        self.publish_dir = Path(publish_dir)
        self.static_dir = Path(static_dir)
        self.layout_dir = Path(layout_dir)

        self.template_env = Environment(
            loader=FileSystemLoader(self.layout_dir)
        )

        self.site_params = {
            "tld": "reveille.xyz",
            "author": "Sakib Hasan",
            "site_url": "https://reveille.xyz",
            "build_time": datetime.datetime.now(),
            "static_dir": self.static_dir.name,
            'now': datetime.datetime.now()
        }


    def setup_output_directory(self):
        if self.publish_dir.exists():
            logging.info("Removing existing publish directory: %s", self.publish_dir)
            shutil.rmtree(self.publish_dir)

        logging.info("Creating publish directory")
        self.publish_dir.mkdir(parents=True, exist_ok=True)

        logging.info("Copying static files")
        shutil.copytree(
            self.static_dir,
            self.publish_dir / self.static_dir.name,
        )


    def fread(self, filepath: Path) -> dict:
        raw_text = filepath.read_text(encoding="utf-8")
        headers, body = self._extract_headers(raw_text)

        is_fixed_page = parse_bool(headers.get("fixed_page"))
        is_draft = parse_bool(headers.get("draft"), default=False)

        content_date = None
        content_time = None

        if not is_fixed_page and not is_draft:
            try:
                content_date = datetime.datetime.strptime(
                    headers["date"], "%Y-%m-%d"
                ).date()
                content_time = datetime.datetime.strptime(
                    headers["time"], "%H:%M"
                ).time()
            except KeyError as exc:
                raise ValueError(
                    f"Missing required header {exc} in {filepath}"
                ) from exc
            except ValueError as exc:
                raise ValueError(
                    f"Invalid date/time format in {filepath}: {exc}"
                ) from exc
        else:
            # Safe defaults for non-post pages
            content_date = datetime.date.min
            content_time = datetime.time.min

        content = {
            **headers,
            "content": markdown.markdown(body),
            "date": content_date,
            "time": content_time,
            "slug": slugify(headers.get("title", filepath.stem)),
            "fixed_page": is_fixed_page,
            "draft": is_draft,
        }

        return content


    def fwrite(self, relative_path: Path, content: str):
        full_path = self.publish_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        logging.info("Writing %s", full_path)
        full_path.write_text(content, encoding="utf-8")

    def _extract_headers(self, text: str):
        headers = {}
        body_lines = []

        lines = text.splitlines()
        header_lines_consumed = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("<!--") and stripped.endswith("-->"):
                inner = stripped[4:-3].strip()
                if ":" not in inner:
                    logging.warning("Malformed header comment: %s", line)
                    header_lines_consumed += 1
                    continue

                key, value = inner.split(":", 1)
                headers[key.strip()] = value.strip()
                header_lines_consumed += 1
            else:
                break

        body_lines = lines[header_lines_consumed:]
        return headers, "\n".join(body_lines)


    # Routing
    def compute_output_path(self, filepath: Path, content: dict) -> Path:
        directory_name = filepath.parent.stem
        date_str = content["date"].strftime("%Y-%m-%d")
        slug = content["slug"]

        if parse_bool(content.get("fixed_page")):
            return Path(slug) / "index.html"

        return Path(f"{directory_name}/{date_str}-{slug}/index.html")


    def generate_pages(self, source_pattern: str, template_name: str):
        generated_items = []

        for filepath in self.content_dir.rglob(source_pattern):
            logging.info("Processing %s", filepath)

            content = self.fread(filepath)
            content.update(self.site_params)

            if parse_bool(content.get("draft"), default=True):
                logging.info("Skipping draft: %s", filepath)
                continue

            output_html = self.template_env.get_template(template_name).render(**content)
            dest_path = self.compute_output_path(filepath, content)
            print('-------------------')
            print(content["title"], dest_path)
            content["url"] = f"/{dest_path.parent}/"
            print(content["url"])
            print('-------------------')
            self.fwrite(dest_path, output_html)

            if not parse_bool(content.get("fixed_page")):
                generated_items.append(content)

        return sorted(generated_items, key=lambda x: x["date"], reverse=True)

    def generate_list_page(self, posts, dest, template_name):
        html = self.template_env.get_template(template_name).render(
            **self.site_params,
            posts=posts,
        )
        self.fwrite(Path(dest), html)

    def generate_custom_404(self, dest, template_name):
        content = {
            "title": "404 - Page Not Found",
            "content": "The page you are looking for does not exist.",
            "fixed_page": "yes",
            **self.site_params,
        }

        html = self.template_env.get_template(template_name).render(**content)
        self.fwrite(Path(dest), html)


    def build(self):
        self.setup_output_directory()

        blog_posts = self.generate_pages("*.md", "post.html")

        self.generate_list_page(
            posts=blog_posts[:10],
            dest="index.html",
            template_name="home.html",
        )

        self.generate_list_page(
            posts=blog_posts,
            dest="all/index.html",
            template_name="all.html",
        )

        self.generate_custom_404(
            dest="404.html",
            template_name="post.html",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    SiteGenerator(
        content_dir="content",
        publish_dir="_site",
        static_dir="static",
        layout_dir="layout",
    ).build()
