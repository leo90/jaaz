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

    # Fix: Don't save masked API keys back to config.
    # If the API key ends with '****', keep the original value.
    current_config = config_service.app_config
    for provider, provider_config in data.items():
        if isinstance(provider_config, dict) and 'api_key' in provider_config:
            new_key = provider_config['api_key']
            if isinstance(new_key, str) and new_key.endswith('****'):
                # SECURITY: Validate prefix matches before restoring
                # Prevents attackers from sending 'X****' to restore arbitrary keys
                original = current_config.get(provider, {}).get('api_key', '')
                if original and len(new_key) >= 4:
                    # Check that the visible prefix matches (user must at least see the first 4 chars)
                    visible_prefix = new_key[:-4]
                    if original.startswith(visible_prefix):
                        provider_config['api_key'] = original
                    # If prefix doesn't match, leave the new value as-is (it will fail validation later)

    res = await config_service.update_config(data)

    # 每次更新配置后，重新初始化工具
    await tool_service.initialize()
    return res
