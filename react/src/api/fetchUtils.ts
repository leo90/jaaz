/**
 * Wrapper around fetch() that checks response.ok before parsing JSON.
 * Throws an Error with status and detail for non-2xx responses.
 */
export async function apiFetch<T = unknown>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(url, options)

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body.detail) detail += `: ${body.detail}`
      else if (body.error) detail += `: ${body.error}`
      else if (body.message) detail += `: ${body.message}`
    } catch {
      // Response body was not JSON, use status text
      detail += `: ${response.statusText}`
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}
