import numpy as np
from PIL import Image
import sys

class ArtisticBinaryConverter:
    def __init__(self):
        # Bayer matrix for ordered dithering
        self.bayer_matrix_4x4 = np.array([
            [ 0, 12,  3, 15],
            [ 8,  4, 11,  7],
            [ 2, 14,  1, 13],
            [10,  6,  9,  5]
        ]) / 16.0

        # Halftone pattern matrix
        self.halftone_matrix = np.array([
            [13,  3, 12,  2],
            [ 1, 15,  4, 14],
            [11,  5, 10,  6],
            [ 7,  9,  8,  0]
        ]) / 16.0

    def floyd_steinberg(self, pixels, threshold=128):
        """Classic Floyd-Steinberg dithering for a more organic look"""
        height, width = pixels.shape
        for y in range(height-1):
            for x in range(width-1):
                old_pixel = pixels[y, x]
                new_pixel = 255 if old_pixel > threshold else 0
                error = old_pixel - new_pixel
                
                pixels[y, x] = new_pixel
                pixels[y, x+1] = pixels[y, x+1] + error * 7/16
                pixels[y+1, x-1] = pixels[y+1, x-1] + error * 3/16
                pixels[y+1, x] = pixels[y+1, x] + error * 5/16
                pixels[y+1, x+1] = pixels[y+1, x+1] + error * 1/16
        return pixels

    def bayer_dither(self, pixels):
        """Bayer ordered dithering for a more geometric, pattern-based look"""
        height, width = pixels.shape
        threshold_map = np.tile(self.bayer_matrix_4x4, 
                              (height//4 + 1, width//4 + 1))[:height, :width]
        return np.where(pixels/255 > threshold_map, 255, 0)

    def halftone(self, pixels):
        """Halftone-style dithering for a comic/newspaper print look"""
        height, width = pixels.shape
        threshold_map = np.tile(self.halftone_matrix,
                              (height//4 + 1, width//4 + 1))[:height, :width]
        return np.where(pixels/255 > threshold_map, 255, 0)

    def contrast_dither(self, pixels, contrast=1.5):
        """High contrast dithering for a bold, graphic look"""
        # Enhance contrast before dithering
        pixels = pixels.astype(float)
        pixels = (pixels - 128) * contrast + 128
        pixels = np.clip(pixels, 0, 255)
        return self.floyd_steinberg(pixels)

    def pixelated_dither(self, pixels, block_size=2):
        """Pixelated dithering for a retro, low-res look"""
        height, width = pixels.shape
        # Reduce resolution
        h_blocks = height // block_size
        w_blocks = width // block_size
        
        reduced = pixels[:h_blocks*block_size, :w_blocks*block_size]
        reduced = reduced.reshape(h_blocks, block_size, w_blocks, block_size)
        reduced = reduced.mean(axis=(1,3))
        
        # Scale back up
        upscaled = np.repeat(np.repeat(reduced, block_size, axis=0), 
                           block_size, axis=1)
        # Apply dithering to the pixelated image
        return self.floyd_steinberg(upscaled)

def convert_image(image_path, style='floyd', **kwargs):
    """
    Convert image to binary using various artistic styles
    
    Args:
        image_path (str): Input image path
        style (str): One of 'floyd', 'bayer', 'halftone', 'contrast', 'pixelated'
        **kwargs: Additional style-specific parameters
    """
    # Initialize converter
    converter = ArtisticBinaryConverter()
    
    # Load and convert image to grayscale
    img = Image.open(image_path).convert('L')
    pixels = np.array(img)
    
    # Apply selected style
    if style == 'bayer':
        processed = converter.bayer_dither(pixels)
    elif style == 'halftone':
        processed = converter.halftone(pixels)
    elif style == 'contrast':
        contrast = kwargs.get('contrast', 1.5)
        processed = converter.contrast_dither(pixels, contrast)
    elif style == 'pixelated':
        block_size = kwargs.get('block_size', 2)
        processed = converter.pixelated_dither(pixels, block_size)
    else:  # default to floyd-steinberg
        processed = converter.floyd_steinberg(pixels)
    
    # Save the result
    binary_image = Image.fromarray(processed.astype(np.uint8))
    binary_image = binary_image.convert('1')
    binary_image.save(image_path)
