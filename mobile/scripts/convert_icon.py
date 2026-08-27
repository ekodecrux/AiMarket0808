from pathlib import Path
from PIL import Image

project = Path("/home/ubuntu/AiMarketMobile")
source = Path("/home/ubuntu/webdev-static-assets/aimarket-nexus-icon.png")
target_directory = project / "assets" / "images"

with Image.open(source) as image:
    rgba = image.convert("RGBA")
    rgba.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    for filename in ("icon.png", "splash-icon.png", "favicon.png", "android-icon-foreground.png"):
        rgba.save(target_directory / filename, format="PNG", optimize=True, compress_level=9)
