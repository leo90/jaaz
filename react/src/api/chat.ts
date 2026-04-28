import { Message, Model } from '@/types/types'
import { ModelInfo, ToolInfo } from './model'
import { apiFetch } from '@/api/fetchUtils'

export const getChatSession = async (sessionId: string) => {
  return apiFetch<Message[]>(`/api/chat_session/${sessionId}`)
}

export const sendMessages = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  textModel: Model
  toolList: ToolInfo[]
  systemPrompt: string | null
}) => {
  return apiFetch<Message[]>(`/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      text_model: payload.textModel,
      tool_list: payload.toolList,
      system_prompt: payload.systemPrompt,
    }),
  })
}

export const cancelChat = async (sessionId: string) => {
  return apiFetch(`/api/cancel/${sessionId}`, {
    method: 'POST',
  })
}
