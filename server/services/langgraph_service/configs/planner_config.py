from typing import List
from .base_config import BaseAgentConfig, HandoffConfig


class PlannerAgentConfig(BaseAgentConfig):
    """规划智能体 - 负责制定执行计划
    """

    def __init__(self) -> None:
        # 简化的系统提示词，避免复杂指令导致模型输出不稳定
        system_prompt = """
You are a planning assistant. Answer in the SAME LANGUAGE as the user's prompt.

YOUR TASK:
1. Use write_plan tool to create a simple execution plan for the user's request
2. After writing the plan, handoff to image_video_creator agent for image/video generation tasks

IMPORTANT:
- Always produce valid JSON when calling tools
- Never output garbage characters, random text, or repeated symbols
- Be concise and clear
"""

        handoffs: List[HandoffConfig] = [
            {
                'agent_name': 'image_video_creator',
                'description': "Transfer to the image/video generation specialist"
            }
        ]

        super().__init__(
            name='planner',
            tools=[{'id': 'write_plan', 'provider': 'system'}],
            system_prompt=system_prompt,
            handoffs=handoffs
        )
