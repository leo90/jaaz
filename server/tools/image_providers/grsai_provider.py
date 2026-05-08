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
                "webHook": "-1",  # return task ID immediately
                "shutProgress": True,
            }

            if input_images and len(input_images) > 0:
                payload["images"] = input_images

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
