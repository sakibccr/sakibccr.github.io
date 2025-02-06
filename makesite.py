import shutil, re, datetime, markdown
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from image_compressor import compress_images
from rich import print
import ipdb

class SiteGenerator:
    def __init__(self, publish_dir='_site',
                 static_dir='static', layout_dir='layout'):
        self.publish_dir = Path(publish_dir)
        self.static_dir = Path(static_dir)
        self.layout_dir = Path(layout_dir)
        self.base_dir = Path(__file__).resolve().parent
        self.template_env = Environment(loader=FileSystemLoader(self.layout_dir))
        self.params = {
            'tld': 'reveille.xyz',
            'author': 'Sakib Hasan',
            'site_url': 'https://reveille.xyz',
            'now': datetime.datetime.now(),
            'static_dir': self.static_dir
        }

    def setup(self):
        if self.publish_dir.exists():
            print('Removing existing publish directory')
            shutil.rmtree(self.publish_dir)
        print('Creating publish directory, copying static files')

        shutil.copytree(self.static_dir, self.publish_dir / self.static_dir)

    def fread(self, filename):
        print(f'Reading {filename}')
        text = Path(filename).read_text(encoding='utf-8')
        date_slug = Path(filename).stem
        match = re.match(r'^(?:(\d{4}-\d{2}-\d{2})-)?(.+)$', date_slug)
        content = {
            'date': datetime.datetime.strptime(match.group(1) or '1970-01-01', '%Y-%m-%d'),
            'slug': match.group(2)
        }
        headers, text = self._extract_headers(text)
        content.update(headers)
        content['content'] = markdown.markdown(text)
        return content
    
    def fwrite(self, dest, content):
        print('Writing', dest)
        self.publish_dir.joinpath(dest).parent.mkdir(parents=True, exist_ok=True)
        self.publish_dir.joinpath(dest).write_text(content, encoding='utf-8')

    def _extract_headers(self, text):
        headers = {}
        for line in text.split('\n'):
            if line.startswith('<!--') and '-->' in line:
                key, value = line.strip('<!-- -->').split(':', 1)
                headers[key.strip()] = value.strip()
            else:
                break
        return headers, '\n'.join(text.split('\n')[len(headers):])

    def compute_dest(self, pattern, filepath, content):
        directory = filepath.parent.stem
        date = content['date'].strftime('%Y-%m-%d')  # read this from a config
        slug = content['slug']
        return Path(pattern.format(directory=directory, date=date, slug=slug))

    def generate_pages(self, src_pattern, layout):
        items = []
        import ipdb; ipdb.set_trace()
        for filepath in self.base_dir.rglob(src_pattern):
            content = self.fread(filepath)
            content.update(self.params)

            if content.get('draft', 'no').lower() in ['true', 'yes', '1']:
                output = self.template_env.get_template(layout).render(**content)
                dest = self.compute_dest('{directory}/{date}-{slug}/index.html', filepath, content)
                content['url'] = dest.parent
                self.fwrite(dest, output)
                items.append(content)
            else:
                print(f'Skipping {filepath}')

        return sorted(items, key=lambda x: x['date'], reverse=True)

    def generate_list_page(self, posts, dest, list_layout):
        content = self.template_env.get_template(list_layout).render(**self.params, posts=posts)
        self.fwrite(dest, content)

    def build(self):
        self.setup()

        # blog posts
        blog_posts = self.generate_pages('*.md', 'post.html')

        # index page
        self.generate_list_page(blog_posts, 'index.html', 'home.html')

if __name__ == '__main__':
    SiteGenerator().build()
    compress_images('_site/static/assets/images')
