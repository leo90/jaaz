import { LLMConfig } from '@/types/types'
import { apiFetch } from '@/api/fetchUtils'

export async function getConfigExists(): Promise<{ exists: boolean }> {
  return apiFetch('/api/config/exists')
}

export async function getConfig(): Promise<{ [key: string]: LLMConfig }> {
  return apiFetch('/api/config')
}

export async function updateConfig(config: {
  [key: string]: LLMConfig
}): Promise<{ status: string; message: string }> {
  return apiFetch('/api/config', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
}

// Update jaaz provider api_key after login
export async function updateJaazApiKey(token: string): Promise<void> {
  try {
    const config = await getConfig()

    if (config.jaaz) {
      config.jaaz.api_key = token
    }

    await updateConfig(config)
  } catch (error) {
    console.error('Error updating jaaz provider api_key:', error)
  }
}

// Clear jaaz provider api_key after logout
export async function clearJaazApiKey(): Promise<void> {
  try {
    const config = await getConfig()

    if (config.jaaz) {
      config.jaaz.api_key = ''
      await updateConfig(config)
    }
  } catch (error) {
    console.error('Error clearing jaaz provider api_key:', error)
  }
}
