from typing import List, Dict, Any, Optional
from langgraph.prebuilt import create_react_agent  # type: ignore
from langgraph.graph.graph import CompiledGraph
from langchain_core.tools import BaseTool
from models.tool_model import ToolInfoJson
from services.langgraph_service.configs.image_vide_creator_config import ImageVideoCreatorAgentConfig
from services.tool_service import tool_service


class AgentManager:
    """智能体管理器 - 负责创建和管理所有智能体

    此类负责协调智能体配置的获取和实际 LangGraph 智能体的创建。
    """

    @staticmethod
    def create_agents(
        model: Any,
        tool_list: List[ToolInfoJson],
        system_prompt: str = ""
    ) -> List[CompiledGraph]:
        """创建所有智能体

        Args:
            model: 语言模型实例
            registered_tools: 已注册的工具名称列表
            system_prompt: 系统提示词

        Returns:
            List[Any]: 创建好的智能体列表
        """
        # 简化架构：只使用 image_video_creator，避免多智能体 handoff 问题
        image_video_creator_config = ImageVideoCreatorAgentConfig(tool_list)
        image_video_creator_agent = AgentManager._create_langgraph_agent(
            model, image_video_creator_config)

        # 只返回一个智能体，避免 planner -> creator 的 handoff 问题
        return [image_video_creator_agent]

    @staticmethod
    def _create_langgraph_agent(
        model: Any,
        config: Any
    ) -> CompiledGraph:
        """根据配置创建单个 LangGraph 智能体

        Args:
            model: 语言模型实例
            config: 智能体配置字典

        Returns:
            Any: 创建好的 LangGraph 智能体实例
        """
        # 获取业务工具
        business_tools: List[BaseTool] = []
        for tool_json in config.tools:
            tool = tool_service.get_tool(tool_json['id'])
            if tool:
                business_tools.append(tool)

        # 创建并返回 LangGraph 智能体（简化版：没有 handoff 工具）
        return create_react_agent(
            name=config.name,
            model=model,
            tools=business_tools,
            prompt=config.system_prompt
        )

    @staticmethod
    def get_last_active_agent(
        messages: List[Dict[str, Any]],
        agent_names: List[str]
    ) -> Optional[str]:
        """获取最后活跃的智能体（简化版：总是返回第一个）"""
        return agent_names[0] if agent_names else None
