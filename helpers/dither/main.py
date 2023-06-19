#!/usr/bin/env python

from pathlib import Path
import click
import os
from PIL import Image
import hitherdither

DEFAULT_THRESHOLD = [96, 96, 96] # this sets the contrast of the final image, rgb
DEFAULT_DITHER_PALETTE = [(25,25,25), (75,75,75),(125,125,125),(175,175,175),(225,225,225),(250,250,250)] # 6 tone palette\
DEFAULT_DITHER_PALETTE = [(85, 85, 85), (27, 27, 27), (240,239,209)]

#11 tone palette, heavier, more detail, less visible dither pattern
#[(0,0,0),(25,25,25),(50,50,50),(75,75,75),(100,100,100),(125,125,125),(150,150,150),(175,175,175),(200,200,200),(225,225,225),(250,250,250)]

#3 tone palette, lighter, heavier dithering effect
# [(85, 85, 85), (27, 27, 27), (240,239,209)]

def get_size(img):
    basewidth = 540
    w, h = img.size
    ratio = basewidth / float(w)
    height = int((float(h)*float(ratio)))
    return (basewidth, height)


@click.command()
@click.option(
    '-i',
    '--input-dir',
    required=True,
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        path_type=Path
    )
)
@click.option(
    '-o',
    '--output-dir',
    required=True,
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
        path_type=Path
    )
)
def dither(input_dir, output_dir):
    if not output_dir.exists():
        output_dir.mkdir()

    for file in input_dir.iterdir():
        out_file = output_dir.joinpath(file.name.replace(file.suffix, '.png'))
        if not out_file.exists():
            try:
                img = Image.open(file).convert('RGB')
                new_size = get_size(img)
                img.thumbnail(new_size, Image.LANCZOS)
                palette = hitherdither.palette.Palette(DEFAULT_DITHER_PALETTE)
                threshold = DEFAULT_THRESHOLD
                img_dithered = hitherdither.ordered.bayer.bayer_dithering(img, palette, threshold, order=8)
                img_dithered.save(out_file, optimize=True)
                click.echo(f'dithering file: {file}')
            except IOError:
                click.echo('what kind of file is this')


if __name__ == "__main__":
    dither()
