from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps


def generate_image_variants(asset):
    """Create responsive WebP derivatives and store their paths in metadata."""
    if asset.media_type != 'image' or not asset.file:
        return asset
    with asset.file.open('rb') as source:
        image = ImageOps.exif_transpose(Image.open(source)).convert('RGB')
        original_width, original_height = image.size
        variants = {}
        for label, max_width in (('thumbnail', 480), ('web', 1600)):
            variant = image.copy()
            variant.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            output = BytesIO()
            variant.save(output, format='WEBP', quality=84, method=6)
            path = f'media-library/variants/{asset.pk}/{label}.webp'
            variants[label] = default_storage.save(path, ContentFile(output.getvalue()))
        asset.metadata = {
            **(asset.metadata or {}),
            'dimensions': {'width': original_width, 'height': original_height},
            'variants': variants,
            'processing': 'ready',
        }
        asset.save(update_fields=['metadata', 'updated_at'])
    return asset
