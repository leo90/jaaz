from typing import Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
from langchain_core.runnables import RunnableConfig
from tools.utils.image_generation_core import generate_image_with_provider


class GenerateImageByNanoBanana2ClInputSchema(BaseModel):
    prompt: str = Field(
        description="Required. The prompt for image generation."
    )
    aspect_ratio: str = Field(
        description="Required. Aspect ratio of the image. Supported: auto, 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 5:4, 4:5, 21:9, 1:4, 4:1, 1:8, 8:1. Default: auto"
    )
    input_images: list[str] | None = Field(
        default=None,
        description="Optional. Reference image URLs or base64 strings for character-consistent generation."
    )
    tool_call_id: Annotated[str, InjectedToolCallId]


@tool("generate_image_by_nano_banana_2_cl_grsai",
      description="Generate an image using Nano Banana 2 CL (Character-Consistent) model by GRSAI. Supports reference images for character-consistent generation. Supports 1K and 2K resolutions.",
      args_schema=GenerateImageByNanoBanana2ClInputSchema)
async def generate_image_by_nano_banana_2_cl_grsai(
    prompt: str,
    aspect_ratio: str,
    config: RunnableConfig,
    tool_call_id: Annotated[str, InjectedToolCallId],
    input_images: list[str] | None = None,
) -> str:
    ctx = config.get('configurable', {})
    canvas_id = ctx.get('canvas_id', '')
    session_id = ctx.get('session_id', '')
    return await generate_image_with_provider(
        canvas_id=canvas_id,
        session_id=session_id,
        provider='grsai',
        model='nano-banana-2-cl',
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        input_images=input_images,
    )


__all__ = ["generate_image_by_nano_banana_2_cl_grsai"]
