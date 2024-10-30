import numpy as np
from PIL import Image
import sys

def convert_to_binary(image_path, threshold=128):
    """
    Convert an image to 1-bit black and white with dithering,
    similar to Return of Obra Dinn's visual style.
    
    Args:
        image_path (str): Path to input image
        threshold (int): Base threshold for converting to binary (0-255)
    """
    # Open and convert image to grayscale
    img = Image.open(image_path).convert('L')
    pixels = np.array(img, dtype=float)
    
    # Get image dimensions
    height, width = pixels.shape
    
    # Floyd-Steinberg dithering
    for y in range(height-1):
        for x in range(width-1):
            old_pixel = pixels[y, x]
            new_pixel = 255 if old_pixel > threshold else 0
            pixels[y, x] = new_pixel
            
            # Calculate quantization error
            error = old_pixel - new_pixel
            
            # Distribute error to neighboring pixels
            pixels[y, x+1] = pixels[y, x+1] + error * 7/16
            pixels[y+1, x-1] = pixels[y+1, x-1] + error * 3/16
            pixels[y+1, x] = pixels[y+1, x] + error * 5/16
            pixels[y+1, x+1] = pixels[y+1, x+1] + error * 1/16
    
    # Convert back to binary image
    binary_image = Image.fromarray(pixels.astype(np.uint8))
    binary_image = binary_image.convert('1')  # Convert to 1-bit
    
    # Save the result
    binary_image.save(image_path)
