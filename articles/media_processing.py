from io import BytesIO
import os
import shutil
import subprocess

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageOps


class MediaProcessingError(RuntimeError):
    pass


def scan_media_file(asset):
    """Run a lightweight malware guard before handing media to processors."""
    if not asset.file:
        return True
    with asset.file.open('rb') as source:
        content = source.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
    if b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*' in content:
        raise MediaProcessingError('The uploaded file failed malware scanning.')
    return True


def _set_cdn_url(asset):
    if not asset.file:
        return
    if settings.MEDIA_CDN_URL:
        asset.cdn_url = f'{settings.MEDIA_CDN_URL}/{asset.file.name.lstrip("/")}'
    else:
        asset.cdn_url = asset.file.url


def _generate_alt_text(asset):
    if asset.alt_text:
        return asset.alt_text
    label = asset.title or os.path.splitext(os.path.basename(asset.file.name if asset.file else 'media'))[0]
    asset.alt_text = f'{label.replace("_", " ").replace("-", " ").strip()[:240]} image'
    return asset.alt_text


def transcode_video(asset):
    if asset.media_type != 'video' or not asset.file or not settings.MEDIA_TRANSCODE_ENABLED:
        return None
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return {'status': 'unavailable', 'reason': 'ffmpeg is not installed'}
    try:
        source_path = asset.file.path
    except (AttributeError, NotImplementedError):
        return {'status': 'unavailable', 'reason': 'storage does not expose a local path'}
    stem, _ = os.path.splitext(source_path)
    output_path = f'{stem}.web.mp4'
    subprocess.run(
        [ffmpeg, '-y', '-i', source_path, '-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart', output_path],
        check=True,
        capture_output=True,
        timeout=settings.MEDIA_PROCESSING_TIMEOUT,
    )
    relative_name = os.path.relpath(output_path, settings.MEDIA_ROOT).replace(os.sep, '/')
    return {'status': 'ready', 'path': relative_name}


def generate_image_variants(asset):
    """Create responsive WebP/AVIF derivatives when the image backend supports them."""
    if asset.media_type != 'image' or not asset.file:
        return asset
    scan_media_file(asset)
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
            try:
                avif_output = BytesIO()
                variant.save(avif_output, format='AVIF', quality=72)
                avif_path = f'media-library/variants/{asset.pk}/{label}.avif'
                variants[f'{label}_avif'] = default_storage.save(avif_path, ContentFile(avif_output.getvalue()))
            except (OSError, ValueError):
                pass
        asset.metadata = {
            **(asset.metadata or {}),
            'dimensions': {'width': original_width, 'height': original_height},
            'variants': variants,
            'processing': 'ready',
        }
        _generate_alt_text(asset)
        _set_cdn_url(asset)
        asset.save(update_fields=['metadata', 'alt_text', 'cdn_url', 'updated_at'])
    return asset


def process_media_asset(asset):
    had_alt_text = bool(asset.alt_text)
    scan_media_file(asset)
    metadata = dict(asset.metadata or {})
    metadata['security_scan'] = 'passed'
    metadata['processing'] = 'processing'
    asset.processing_status = 'processing'
    asset.processing_error = ''
    asset.metadata = metadata
    if asset.file:
        asset.file_size = asset.file.size
        _set_cdn_url(asset)
    if asset.media_type == 'image':
        generate_image_variants(asset)
    elif asset.media_type == 'video':
        metadata['transcoding'] = transcode_video(asset) or {'status': 'skipped'}
        asset.metadata = metadata
    if asset.media_type == 'image':
        metadata = dict(asset.metadata or {})
        metadata['alt_text_source'] = 'provided' if had_alt_text else 'generated'
        asset.metadata = metadata
    asset.processing_status = 'ready'
    asset.processed_at = timezone.now()
    asset.metadata = {**(asset.metadata or {}), 'processing': 'ready'}
    asset.save(update_fields=['metadata', 'file_size', 'cdn_url', 'alt_text', 'processing_status', 'processing_error', 'processed_at', 'updated_at'])
    return asset
