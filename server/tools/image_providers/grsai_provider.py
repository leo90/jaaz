import os
import asyncio
import traceback
from typing import Optional, Any
from .image_base_provider import ImageProviderBase
from ..utils.image_utils import get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR, config_service
from utils.http_client import HttpClient


class GrsaiProvider(ImageProviderBase):
    """GRSAI Nano Banana image generation provider"""

    def _build_headers(self) -> dict[str, str]:
        config = config_service.app_config.get('grsai', {})
        api_key = str(config.get("api_key", ""))
        if not api_key:
            raise ValueError("GRSAI API key is not configured")
        return {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

    def _get_base_url(self) -> str:
        config = config_service.app_config.get('grsai', {})
        url = str(config.get("url", "https://grsai.dakka.com.cn"))
        return url.rstrip('/')

    def _map_aspect_ratio(self, aspect_ratio: str) -> str:
        # Nano Banana uses "1:1", "16:9" etc. directly, or "auto"
        ratio_map = {
            "1:1": "1:1", "16:9": "16:9", "9:16": "9:16",
            "4:3": "4:3", "3:4": "3:4", "3:2": "3:2",
            "2:3": "2:3", "5:4": "5:4", "4:5": "4:5", "21:9": "21:9",
        }
        return ratio_map.get(aspect_ratio, "auto")

    async def _convert_images_to_public_urls(self, input_images: list[str]) -> list[str]:
        """
        Convert local filenames/base64 data URLs to public HTTP URLs.

        Graceful degradation: if any upload fails, skip reference images entirely
        (don't fail the whole generation request).
        """
        from tools.utils.image_uploader import upload_image_to_public
        from services.config_service import FILES_DIR
        import os

        # 过滤空字符串
        input_images = [img for img in input_images if img and img.strip()]
        if not input_images:
            print("GRSAI: 过滤后没有有效的参考图片")
            return []

        public_urls = []
        successful_count = 0

        for image_source in input_images:
            # Resolve full path if it's a filename
            if not image_source.startswith("data:"):
                full_path = os.path.join(FILES_DIR, image_source)
                if not os.path.exists(full_path):
                    print(f"GRSAI: Image file not found, skipping: {full_path}")
                    continue
                image_source = full_path

            # Upload to public hosting
            try:
                result = await upload_image_to_public(image_source, timeout_seconds=30)
                if result.success:
                    print(f"GRSAI: Uploaded reference image to {result.service}: {result.url}")
                    public_urls.append(result.url)
                    successful_count += 1
                else:
                    print(f"GRSAI: Failed to upload reference image: {result.error}")
            except Exception as e:
                print(f"GRSAI: Exception uploading reference image: {e}")

        if not public_urls and input_images:
            print("GRSAI: All reference image uploads failed, proceeding without reference images")
        elif successful_count < len(input_images):
            print(f"GRSAI: Partial upload success: {successful_count}/{len(input_images)} images uploaded")

        return public_urls

    async def _poll_for_result(self, task_id: str, headers: dict[str, str]) -> dict:
        base_url = self._get_base_url()
        async with HttpClient.create_aiohttp() as session:
            for attempt in range(120):  # max 120 seconds
                await asyncio.sleep(1)
                try:
                    async with session.post(
                        f"{base_url}/v1/draw/result",
                        json={"id": task_id},
                        headers=headers,
                    ) as resp:
                        result = await resp.json()
                        data = result.get("data", {})
                        status = data.get("status")

                        if status == "succeeded":
                            return data
                        if status == "failed":
                            failure = data.get("failure_reason", "")
                            error = data.get("error", "")
                            raise Exception(
                                f"GRSAI generation failed: {failure} - {error}"
                            )
                except Exception as e:
                    # Retry on connection errors, but fail after 5 consecutive errors
                    if attempt > 5 and "connection" in str(e).lower():
                        raise Exception(
                            f"Connection error polling GRSAI result at {base_url}/v1/draw/result: {e}"
                        ) from e
                    # For other errors, re-raise immediately
                    if "connection" not in str(e).lower():
                        raise

            raise Exception("GRSAI image generation timeout (120s)")

    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_images: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> tuple[str, int, int, str]:
        try:
            headers = self._build_headers()
            base_url = self._get_base_url()

            payload: dict[str, Any] = {
                "model": model,
                "prompt": prompt,
                "aspectRatio": self._map_aspect_ratio(aspect_ratio),
                "webhook": "-1",  # return task ID immediately
                "shutProgress": True,
                "urls": [],
            }

            if input_images and len(input_images) > 0:
                print(f"GRSAI: 开始处理 {len(input_images)} 张输入图片")
                # Upload reference images to public hosting and get URLs
                public_urls = await self._convert_images_to_public_urls(input_images)
                payload["urls"] = public_urls
                print(f"GRSAI: 最终发送到 API 的参考图片数量: {len(public_urls)}")
                for i, url in enumerate(public_urls, 1):
                    print(f"GRSAI: 图片 {i}: {url}")

            # Submit generation task
            try:
                async with HttpClient.create_aiohttp() as session:
                    async with session.post(
                        f"{base_url}/v1/draw/nano-banana",
                        json=payload,
                        headers=headers,
                    ) as resp:
                        resp_json = await resp.json(content_type=None)
                        if resp_json.get("code") != 0:
                            raise Exception(
                                f"GRSAI API error: {resp_json.get('msg', resp_json)}"
                            )
                        task_id = resp_json["data"]["id"]
            except Exception as e:
                raise Exception(
                    f"Failed to submit GRSAI generation task to {base_url}/v1/draw/nano-banana: {e}"
                ) from e

            # Poll for result
            try:
                result_data = await self._poll_for_result(task_id, headers)
            except Exception as e:
                raise Exception(
                    f"Failed to poll for GRSAI result (task_id: {task_id}): {e}"
                ) from e

            # Extract image URL from results
            results = result_data.get("results", [])
            if not results or not results[0].get("url"):
                raise Exception("GRSAI: no image URL in response")

            image_url = results[0]["url"]

            # Save the image
            try:
                image_id = generate_image_id()
                mime_type, width, height, extension = await get_image_info_and_save(
                    image_url,
                    os.path.join(FILES_DIR, f'{image_id}'),
                )
                filename = f'{image_id}.{extension}'
                return mime_type, width, height, filename
            except Exception as e:
                raise Exception(
                    f"Failed to save image from {image_url}: {e}"
                ) from e

        except Exception as e:
            print('Error generating image with GRSAI:', e)
            traceback.print_exc()
            raise e
