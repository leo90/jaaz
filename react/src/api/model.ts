import { apiFetch } from '@/api/fetchUtils'

export type ModelInfo = {
  provider: string
  model: string
  type: 'text' | 'image' | 'tool' | 'video'
  url: string
}

export type ToolInfo = {
  provider: string
  id: string
  display_name?: string | null
  type?: 'image' | 'tool' | 'video'
}

export async function listModels(): Promise<{
  llm: ModelInfo[]
  tools: ToolInfo[]
}> {
  let modelsResp: ModelInfo[] = []
  let toolsResp: ToolInfo[] = []

  try {
    modelsResp = await apiFetch<ModelInfo[]>('/api/list_models')
  } catch (err) {
    console.error('Failed to fetch models:', err)
  }

  try {
    toolsResp = await apiFetch<ToolInfo[]>('/api/list_tools')
  } catch (err) {
    console.error('Failed to fetch tools:', err)
  }

  return {
    llm: modelsResp,
    tools: toolsResp,
  }
}
