const BASE_URL = import.meta.env.VITE_API_URL || ''

export class ApiError extends Error {
  status: number
  details: unknown

  constructor(status: number, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    let details: unknown
    let message = `API error: ${res.status}`
    try {
      const body = await res.json()
      details = body
      message = body.message ?? body.error ?? message
    } catch {
      // response body wasn't JSON – keep the generic message
    }
    throw new ApiError(res.status, message, details)
  }
  return res.json()
}

export async function apiMutate<T>(url: string, body?: unknown): Promise<T> {
  return apiFetch<T>(url, {
    method: 'POST',
    body: body != null ? JSON.stringify(body) : undefined,
  })
}
