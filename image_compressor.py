from PIL import Image, ImageOps
import hitherdither
from pathlib import Path
import os
import logging
from obra_dinn import convert_to_binary
from dithering_one_bit import convert_image
# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def resize_image(image_obj, width=768):
    """Resize image while maintaining the aspect ratio."""
    aspect_ratio = image_obj.height / image_obj.width
    new_height = int(width * aspect_ratio)
    return image_obj.resize((width, new_height), Image.Resampling.LANCZOS)

def convert_to_monochrome(image_obj):
    """Convert the image to monochrome (black and white)."""
    gray_image = image_obj.convert('L')  # '1' mode for monochrome
    tinted_image = ImageOps.colorize(gray_image, black="#260707", white="#fe4a08")
    return tinted_image

def dither(image_obj):
    palette = hitherdither.palette.Palette(
        [0x2d1f01, 0xa37302, 0xfcfcfc, 0xf7ae02]
    )
    threshold = [96, 96, 96]
    img_dithered = hitherdither.ordered.bayer.bayer_dithering(image_obj, palette, threshold, order=8) #see hither dither documentation for different dithering algos
    return img_dithered

def process_image(image_path):
    """Resize, grayscale, and compress the image."""
    try:
        with Image.open(image_path) as img:
            original_size = os.path.getsize(image_path)

            # Resize and convert the image
            resized_img = resize_image(img)
#            img = convert_to_monochrome(resized_img)
            img = dither(resized_img)

            # Save the image back to its original path with compression
            img.convert('RGB').save(image_path, format=img.format, quality=50, optimize=True)

            # Log the compression details
            compressed_size = os.path.getsize(image_path)
            logging.info(f"Compressed {image_path.name}: {original_size / 1024:.2f} KB -> {compressed_size / 1024:.2f} KB")

    except Exception as e:
        logging.error(f"Error processing {image_path}: {e}")

def compress_images(directory_path):
    """Iterate over images in a directory and compress them."""
    image_extensions = {'.jpg', '.jpeg', '.png'}  # Add common extensions
    directory = Path(directory_path)

    # Iterate through all image files in the directory recursively
    for image_path in directory.rglob('*'):
        if image_path.suffix.lower() in image_extensions:
            # process_image(image_path)
            convert_to_binary(image_path)
            # 'bayer', 'halftone', 'contrast', 'pixelated'
            # convert_image(image_path, style="bayer")

# Example usage:
# compress_images_in_directory('/path/to/images')
