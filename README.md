This is my website. I use a small Python script to generate the posts from markdown files. The inspiration for this came from Sunaina Pai's awesome [makesite.py](https://github.com/sunainapai/makesite).

The website can be viewed [here](https://reveille.xyz/).

## Writing and publishing from Android

1. Open this repository as an Obsidian vault. Pull using the Git plugin before writing, especially when switching devices.
2. Create a note in `content/blog/` and insert the `NewPost` template. Its properties start with `draft: true`.
3. Write the post. Set a permanent `slug` such as `a-walk-in-dhaka` before publishing. You can edit properties in Obsidian without editing YAML directly.
4. Set `draft` to `false` when ready, then commit and push to `main` using the Git plugin. Keep Obsidian open until the push finishes.
5. Check the repository's Actions tab for the **Build site and deploy** result. A successful push alone does not mean the site deployed.

Posts without a draft property stay unpublished. Published posts require a title and a valid `YYYY-MM-DD` date; `time` is optional and defaults to midnight in Asia/Dhaka. Quote times in raw YAML, e.g. `time: "17:13"`. Future dates do not schedule publication: `draft: false` publishes immediately.

Post URLs are `/blog/<slug>/`. A blank slug falls back to the filename, not the title. Keep an explicit slug unchanged to preserve the URL when renaming a note. Fixed pages use `fixed_page: true` and live at `/<slug>/`. Duplicate URLs and invalid metadata fail the build before replacing local output.

**Drafts are not private storage.** A public repository exposes committed drafts and their history. Everything in `static/`, including unused or draft attachments, is copied to the public website. Keep private notes and private attachments outside this repository.

## Links and images

Obsidian is configured to create standard Markdown links and put attachments in `static/assets/images/`. The generator supports:

- Standard Markdown links to notes, such as `[Another post](Another%20post.md)`.
- Wikilinks, including aliases and headings: `[[Another post|Read more]]`, `[[Another post#A heading]]`.
- Standard Markdown images and Obsidian image embeds such as `![[photo.webp]]`. Use folder paths when filenames are ambiguous.
- Fenced code, tables, footnotes, and heading IDs.

Links to unpublished notes, missing local note links, and missing Markdown images fail the build with a source filename. Note/block transclusion (`![[Some note]]`), block references, callouts, and Obsidian image sizing syntax are not implemented. Raw HTML is passed through; its links are not validated or rewritten, so use root-relative or absolute URLs there.

For phone photos, resize/compress a copy **before adding it to the vault**. Aim for at most 1600 pixels on the longest edge and under 500 KB. The build rejects images above 2 MiB as a reminder, but this cannot remove large files already pushed into Git history. Keep originals outside the vault.

On a computer (or a Python environment on Android), the included importer creates a WebP copy, corrects orientation, and strips metadata including GPS:

```sh
.venv/bin/python scripts/import_image.py /path/to/original.jpg static/assets/images/photo.webp
```

It preserves the original and refuses to overwrite an existing destination. Animated images should be prepared separately. Existing site images are already small and were left intact.

## Sync settings

Obsidian's desktop/mobile workspace files and plugin `data.json` files are local-only. Plugin code and shared vault preferences remain versioned. Configure Git authentication and sync preferences separately on each device; do not commit credentials.

Before pulling the change that stops tracking these files on another device, close Obsidian and back up its workspace and plugin settings outside the vault. Git may remove the formerly tracked copies during that first pull; restore your backup afterward. Subsequent edits will be ignored by Git.

Pull before editing on a different device, and finish a push before switching. If a conflict occurs, resolve it on a computer when practical. Avoid running multiple sync systems over the same vault.

## Local preview and checks

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
./run.sh
```

Open `http://127.0.0.1:8000`. The preview script stops if the build fails. Generated files live in ignored `_site/`; source content is never rewritten by the build.

## Deployment and subscriptions

Pushes to `main` affecting site sources run tests, build, and deploy to GitHub Pages. Obsidian-only and documentation-only commits do not deploy. Pull requests validate without deploying, and Actions also supports a manual run. Deployments on the same branch are serialized. GitHub Pages must use **GitHub Actions** as its publishing source.

RSS is at `/feed.xml`, includes the latest 20 published posts with full content, and is linked from every page. Feed dates use Asia/Dhaka and Markdown links/images become absolute URLs. Canonical URLs are generated for each post and listing.
