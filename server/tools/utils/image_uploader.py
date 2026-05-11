"""
Image uploader module for uploading local files/base64 to public hosting services.
Used by GRSAI provider to convert local reference images to publicly accessible URLs.
"""

import os
import base64
import io
import aiohttp
from typing import Optional, List, Dict
from dataclasses import dataclass
from PIL import Image
from utils.http_client import HttpClient
from services.config_service import config_service


@dataclass
class ImageUploadResult:
    """Result of an image upload attempt"""
    success: bool
    url: Optional[str] = None
    error: Optional[str] = None
    service: Optional[str] = None


def _is_base64_data_url(source: str) -> bool:
    """Check if input is a base64 data URL"""
    return source.startswith("data:")


def _extract_base64_data(data_url: str) -> tuple[bytes, str]:
    """Extract raw bytes and mime type from base64 data URL"""
    # Format: data:image/png;base64,...
    header_part, data_part = data_url.split(",", 1)
    mime_type = header_part.split(";")[0].replace("data:", "")
    raw_data = base64.b64decode(data_part)
    return raw_data, mime_type


async def _upload_to_catbox(
    file_path_or_data: str,
    is_base64: bool,
    timeout_seconds: int = 30
) -> ImageUploadResult:
    """
    Upload image to catbox.moe (no auth required, 200MB/file limit)

    API: https://catbox.moe/tools.php
    """
    url = "https://catbox.moe/user/api.php"

    try:
        async with HttpClient.create_aiohttp() as session:
            # Prepare file data
            if is_base64:
                raw_data, _ = _extract_base64_data(file_path_or_data)
                file_data = io.BytesIO(raw_data)
                filename = "image.png"  # Catbox doesn't care about filename
            else:
                if not os.path.exists(file_path_or_data):
                    return ImageUploadResult(
                        success=False,
                        error=f"File not found: {file_path_or_data}",
                        service="catbox"
                    )
                with open(file_path_or_data, 'rb') as f:
                    file_data = io.BytesIO(f.read())
                filename = os.path.basename(file_path_or_data)

            # Build multipart form
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('fileToUpload', file_data, filename=filename)

            # Upload
            async with session.post(
                url,
                data=data,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds)
            ) as resp:
                if resp.status == 200:
                    result_url = await resp.text()
                    if result_url.startswith("http"):
                        return ImageUploadResult(
                            success=True,
                            url=result_url.strip(),
                            service="catbox"
                        )
                    else:
                        return ImageUploadResult(
                            success=False,
                            error=f"Catbox API error: {result_url}",
                            service="catbox"
                        )
                else:
                    error_text = await resp.text()
                    return ImageUploadResult(
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}",
                        service="catbox"
                    )
    except Exception as e:
        return ImageUploadResult(
            success=False,
            error=str(e),
            service="catbox"
        )


async def _upload_to_vim_cn(
    file_path_or_data: str,
    is_base64: bool,
    timeout_seconds: int = 30
) -> ImageUploadResult:
    """
    Upload image to vim-cn.com (Chinese service, no auth required)
    """
    url = "https://img.vim-cn.com/"

    try:
        async with HttpClient.create_aiohttp() as session:
            # Prepare file data
            if is_base64:
                raw_data, _ = _extract_base64_data(file_path_or_data)
                file_data = io.BytesIO(raw_data)
                filename = "image.png"
            else:
                if not os.path.exists(file_path_or_data):
                    return ImageUploadResult(
                        success=False,
                        error=f"File not found: {file_path_or_data}",
                        service="vim_cn"
                    )
                with open(file_path_or_data, 'rb') as f:
                    file_data = io.BytesIO(f.read())
                filename = os.path.basename(file_path_or_data)

            # Build multipart form
            data = aiohttp.FormData()
            data.add_field('file', file_data, filename=filename)

            # Upload
            async with session.post(
                url,
                data=data,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds)
            ) as resp:
                if resp.status == 200:
                    result_url = await resp.text()
                    result_url = result_url.strip()
                    # vim-cn returns just the path, prepend https
                    if result_url.startswith("//"):
                        result_url = "https:" + result_url
                    elif result_url.startswith("/"):
                        result_url = "https://img.vim-cn.com" + result_url
                    return ImageUploadResult(
                        success=True,
                        url=result_url,
                        service="vim_cn"
                    )
                else:
                    error_text = await resp.text()
                    return ImageUploadResult(
                        success=False,
                        error=f"HTTP {resp.status}: {error_text}",
                        service="vim_cn"
                    )
    except Exception as e:
        return ImageUploadResult(
            success=False,
            error=str(e),
            service="vim_cn"
        )


async def upload_image_to_public(
    image_source: str,
    preferred_services: Optional[List[str]] = None,
    timeout_seconds: int = 30
) -> ImageUploadResult:
    """
    Upload an image to public hosting service with fallback mechanism.

    Args:
        image_source: Local filename (e.g., "im_xxx.jpg") OR base64 data URL
        preferred_services: Ordered list of services to try (defaults to config)
        timeout_seconds: Timeout per upload attempt

    Returns:
        ImageUploadResult with public URL on success, or error details
    """
    # Determine if source is base64 or local file
    is_base64 = _is_base64_data_url(image_source)
    is_local_file = not is_base64

    # Resolve full path if it's a local file
    if is_local_file and not os.path.isabs(image_source):
        from services.config_service import FILES_DIR
        image_source = os.path.join(FILES_DIR, image_source)

    # Get default service order from config
    if preferred_services is None:
        hosting_config = config_service.app_config.get('image_hosting', {})
        preferred_order = hosting_config.get('preferred_order', 'catbox,vim_cn')
        preferred_services = [s.strip() for s in preferred_order.split(',')]

    # Try each service in order
    last_error = None
    for service in preferred_services:
        service = service.lower().strip()

        if service == 'catbox':
            result = await _upload_to_catbox(image_source, is_base64, timeout_seconds)
            if result.success:
                return result
            last_error = result.error
            print(f"Image uploader: catbox failed: {result.error}, trying next...")

        elif service == 'vim_cn':
            result = await _upload_to_vim_cn(image_source, is_base64, timeout_seconds)
            if result.success:
                return result
            last_error = result.error
            print(f"Image uploader: vim_cn failed: {result.error}, trying next...")

        else:
            print(f"Image uploader: Unknown service '{service}', skipping")

    # All services failed
    return ImageUploadResult(
        success=False,
        error=f"All upload services failed. Last error: {last_error}",
        service=None
    )


