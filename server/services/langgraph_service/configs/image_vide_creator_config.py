from typing import List

from models.tool_model import ToolInfoJson
from .base_config import BaseAgentConfig, HandoffConfig

# 简化的系统提示词，避免过长和复杂指令导致模型输出乱码
system_prompt = """
You are an image and video generation assistant.

YOUR TASK:
- Generate high-quality images and videos based on user requests
- Use the available tools to create images and videos
- Always produce valid JSON when calling tools

IMPORTANT RULES:
1. Call the appropriate image/video generation tool directly
2. Create detailed, professional prompts for generation
3. If input images are provided, use the input_images parameter
4. Always output valid JSON, never output garbage characters or random text

Be concise and professional. Focus on generating good results.
"""

class ImageVideoCreatorAgentConfig(BaseAgentConfig):
    def __init__(self, tool_list: List[ToolInfoJson]) -> None:
        # 图像设计智能体不需要切换到其他智能体
        handoffs: List[HandoffConfig] = []

        super().__init__(
            name='image_video_creator',
            tools=tool_list,
            system_prompt=system_prompt,
            handoffs=handoffs
        )
