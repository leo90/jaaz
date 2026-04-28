import { compressImageFile } from '@/utils/imageUtils'
import { apiFetch } from '@/api/fetchUtils'

export async function uploadImage(
  file: File
): Promise<{ file_id: string; width: number; height: number; url: string }> {
  // Compress image before upload
  const compressedFile = await compressImageFile(file)

  const formData = new FormData()
  formData.append('file', compressedFile)
  return apiFetch('/api/upload_image', {
    method: 'POST',
    body: formData,
  })
}
