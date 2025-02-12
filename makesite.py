import shutil, re, datetime, markdown
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from utils import compress_images, generate_thumbnails
from rich import print

class SiteGenerator:
    def __init__(self, publish_dir, static_dir, layout_dir):
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

        if content.get('fixed_page', 'no') in ['true', 'yes', '1']:
            return Path(f'{slug}/index.html')

        return Path(pattern.format(directory=directory, date=date, slug=slug))

    def generate_pages(self, src_pattern, layout):
        items = []
        for filepath in self.base_dir.rglob(src_pattern):
            content = self.fread(filepath)
            content.update(self.params)

            if content.get('draft', 'yes').lower() in ['false', 'no', '0']:
                output = self.template_env.get_template(layout).render(**content)
                dest = self.compute_dest('{directory}/{date}-{slug}/index.html', filepath, content)
                content['url'] = dest.parent
                self.fwrite(dest, output)
                if content.get('fixed_page', 'no').lower() not in ['true', 'yes', '1']:
                    items.append(content)
            else:
                print(f'Skipping {filepath}')

        return sorted(items, key=lambda x: x['date'], reverse=True)

    def generate_list_page(self, posts, dest, list_layout):
        content = self.template_env.get_template(list_layout).render(**self.params, posts=posts)
        self.fwrite(dest, content)

    def generate_custom_404(self, dest, layout):
        custom_404_content = {
            'title': '404 - Page Not Found',
            'content': 'The page you are looking for does not exist.',
            'fixed_page': 'yes'
        }
        custom_404_content.update(self.params)
        output = self.template_env.get_template(layout).render(**custom_404_content)
        self.fwrite(dest, output)
    
    def generate_gallery(self, name, layout):
        src_dir = self.base_dir / name

        images_dir = self.publish_dir / name / 'images'
        images_dir.mkdir(parents=True, exist_ok=True)
        # copy images from src_dir to images_dir
        for img in src_dir.iterdir():
            if img.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                shutil.copy(img, images_dir)

        thumbnails_dir = self.publish_dir / name / 'thumbnails'
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        generate_thumbnails(images_dir, thumbnails_dir)

        images = [img.name for img in images_dir.iterdir() if img.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']]

        self.params.update()

        gallery_content = {
            'images': images,
            'thumbnail_dir': thumbnails_dir,
            'name': name,
            'count': len(images)
        }

        gallery_content.update(self.params)

        output = self.template_env.get_template(layout).render(gallery_content)

        self.fwrite(f'{name}/index.html', output)

        print('Gallery generated at', name)


    def build(self):
        self.setup()

        # blog posts
        blog_posts = self.generate_pages('*.md', 'post.html')

        # index page
        self.generate_list_page(blog_posts, 'index.html', 'home.html')

        # custom 404 page
        self.generate_custom_404('404.html', 'post.html')

        # generate gallery
        self.generate_gallery('photos', 'gallery.html')

if __name__ == '__main__':
    publish_dir='_site'
    static_dir='static'
    layout_dir='layout'
    SiteGenerator(publish_dir=publish_dir,
                 static_dir=static_dir,
                 layout_dir=layout_dir).build()
    compress_images('_site/static/assets/images')
    compress_images('_site/photos/images')
