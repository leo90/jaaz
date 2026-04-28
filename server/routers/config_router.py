import copy
from fastapi import APIRouter, Request
from services.config_service import config_service
# from tools.video_models_dynamic import register_video_models  # Disabled video models
from services.tool_service import tool_service

router = APIRouter(prefix="/api/config")


@router.get("/exists")
async def config_exists():
    return {"exists": config_service.exists_config()}


@router.get("")
async def get_config():
    # Return config with api_key fields masked to prevent credential exposure
    config = copy.deepcopy(config_service.app_config)
    for provider, provider_config in config.items():
        if isinstance(provider_config, dict) and 'api_key' in provider_config:
            key = provider_config['api_key']
            if key and len(key) > 4:
                provider_config['api_key'] = key[:4] + '****'
            elif key:
                provider_config['api_key'] = '****'
    return config


@router.post("")
async def update_config(request: Request):
    data = await request.json()
    res = await config_service.update_config(data)

    # 每次更新配置后，重新初始化工具
    await tool_service.initialize()
    return res
