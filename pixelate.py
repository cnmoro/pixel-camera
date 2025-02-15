from tempfile import TemporaryDirectory
from PIL import Image, ImageEnhance
import subprocess, cv2, os

def load_palette_from_file(palette_file_path):
    """
    Load a color palette from a file.
    Each line in the file should contain a color in hexadecimal format (e.g., #fff2e5).
    Parameters:
        palette_file_path (str): Path to the palette file.
    Returns:
        list: List of RGB tuples representing the palette colors.
    """
    palette = []
    try:
        with open(palette_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line.startswith('#'):
                    line = line.lstrip('#')
                # Convert hex color to RGB tuple
                rgb = tuple(int(line[i:i+2], 16) for i in (0, 2, 4))
                palette.append(rgb)
    except FileNotFoundError:
        print(f"Palette file '{palette_file_path}' not found. Using default quantization.")
        return None
    return palette

def pixelate_image(
    input_path, output_path, target_width=256, palette_size=64, pixel_scale=8, brightness_factor=1.0, contrast_factor=1.0, palette_file=None
):
    """
    Simulate the Pixless camera's image processing pipeline while preserving the original aspect ratio.
    Adjusts brightness and contrast before pixelating.
    Parameters:
        input_path (str): Path to the input image.
        output_path (str): Path to save the output PNG file.
        target_width (int): Target width for the pixelation.
        palette_size (int): Number of colors in the palette (used if no palette file is provided).
        pixel_scale (int): Enlargement factor for each pixel.
        brightness_factor (float): Brightness adjustment factor (1.0 = no change, <1.0 = darker, >1.0 = brighter).
        contrast_factor (float): Contrast adjustment factor (1.0 = no change, <1.0 = lower contrast, >1.0 = higher contrast).
        palette_file (str): Path to a file containing a custom color palette (optional).
    """
    # Load image and convert to RGB
    image = Image.open(input_path).convert("RGB")
    
    # Adjust brightness
    if brightness_factor != 1.0:
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(brightness_factor)
    
    # Adjust contrast
    if contrast_factor != 1.0:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(contrast_factor)
    
    # Calculate the aspect ratio
    original_width, original_height = image.size
    aspect_ratio = original_height / original_width
    
    # Calculate the target height to maintain the aspect ratio
    target_height = int(target_width * aspect_ratio)
    
    # Resize image to target resolution while preserving aspect ratio
    image = image.resize((target_width, target_height), resample=Image.NEAREST)
    
    # Quantize image
    if palette_file:
        palette = load_palette_from_file(palette_file)
        if palette:
            # Create a palette image from the loaded colors
            palette_image = Image.new("P", (1, 1))
            palette_image.putpalette([color for rgb in palette for color in rgb])
            # Quantize the image using the custom palette and disable dithering
            image = image.quantize(palette=palette_image, dither=Image.NONE)
        else:
            # Fallback to default quantization if palette file is not found
            image = image.quantize(colors=palette_size, method=Image.MEDIANCUT, dither=Image.NONE)
    else:
        # Use default quantization if no palette file is provided
        image = image.quantize(colors=palette_size, method=Image.MEDIANCUT, dither=Image.NONE)
    
    # Enlarge each pixel to simulate blocky look
    enlarged_width = target_width * pixel_scale
    enlarged_height = target_height * pixel_scale
    image = image.resize((enlarged_width, enlarged_height), resample=Image.NEAREST)
    
    # Save as a PNG with lossless compression
    image.save(output_path, format="PNG")

def find_framerate(input_path):
    video = cv2.VideoCapture(input_path)
    return video.get(cv2.CAP_PROP_FPS)

def pixelate_video(
    input_path,
    output_path,
    target_width=256,
    palette_size=64,
    pixel_scale=8,
    brightness_factor=1.0,
    contrast_factor=1.0,
    palette_file=None,
    fps=30
):
    """
    Pixelate a video file using the same process as pixelate_image for each frame.
    
    Parameters:
        input_path (str): Path to the input video file.
        output_path (str): Path to save the output video file.
        target_width (int): Target width for pixelation (same as in pixelate_image).
        palette_size (int): Number of colors in the palette (same as in pixelate_image).
        pixel_scale (int): Enlargement factor for each pixel (same as in pixelate_image).
        brightness_factor (float): Brightness adjustment factor (same as in pixelate_image).
        contrast_factor (float): Contrast adjustment factor (same as in pixelate_image).
        palette_file (str): Path to a custom color palette file (same as in pixelate_image).
        fps (int): Frames per second for the output video.
    """
    detected_framerate = find_framerate(input_path)

    if fps > detected_framerate:
        fps = detected_framerate
    
    print(f"Detected FPS: {detected_framerate}, Using FPS: {fps}")

    # Create a temporary directory to store processed frames
    with TemporaryDirectory() as temp_dir:
        # Open the video file
        video = cv2.VideoCapture(input_path)
        
        frame_count = 0
        while True:
            # Read a frame from the video
            ret, frame = video.read()
            if not ret:
                break
            
            # Convert frame from BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Save the frame as a temporary image
            temp_image_path = os.path.join(temp_dir, f"frame_{frame_count:05d}.png")
            cv2.imwrite(temp_image_path, frame_rgb)

            # Pixelate the frame
            output_image_path = os.path.join(temp_dir, f"frame_{frame_count:05d}_pixelated.png")
            pixelate_image(
                input_path=temp_image_path,
                output_path=output_image_path,
                target_width=target_width,
                palette_size=palette_size,
                pixel_scale=pixel_scale,
                brightness_factor=brightness_factor,
                contrast_factor=contrast_factor,
                palette_file=palette_file
            )
            
            frame_count += 1
        
        video.release()
        
        # Use FFmpeg to combine the pixelated frames into a video
        ffmpeg_command = [
            "ffmpeg",
            "-framerate", str(fps),
            "-i", os.path.join(temp_dir, "frame_%05d_pixelated.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        
        subprocess.run(ffmpeg_command, check=True)

# Example usage
input_image_path = "samples/brabham.jpg"  # Replace with the path to your input image
output_image_path = f"{input_image_path.split('.')[0]}_pixelated.png"  # Replace with the path to save the output
palette_file_path = "palettes/digital-paper.txt"  # Replace with the path to your palette file (optional)

pixelate_image(
    input_path=input_image_path,
    output_path=output_image_path,
    target_width=256,
    palette_size=4,
    pixel_scale=4,
    brightness_factor=1.0,          # Increase brightness by 20%
    contrast_factor=1.5,            # Increase contrast by 10%
    palette_file=palette_file_path  # Optional: Path to a custom palette file
)

# # Example usage
# input_video_path = "my_video.mp4"  # Replace with the path to your input image
# output_video_path = f"{input_image_path.split('.')[0]}_pixelated.mp4"  # Replace with the path to save the output
# palette_file_path = "palettes/oil-6.txt"  # Replace with the path to your palette file (optional)

# pixelate_video(
#     input_path=input_video_path,
#     output_path=output_video_path,
#     target_width=256,
#     palette_size=4,
#     pixel_scale=8,
#     brightness_factor=1.0,
#     contrast_factor=1.5,
#     palette_file=palette_file_path,
#     fps=30
# )
