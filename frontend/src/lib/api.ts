import type { components } from './api-types'

type Schemas = components['schemas']
export type Me = Schemas['Me']
export type Account = Schemas['AccountRead']
export type Media = Schemas['MediaRead']
export type Target = Schemas['TargetRead']
export type TargetStatus = Schemas['TargetStatus']
export type Platform = Schemas['Platform']
export type Orientation = Schemas['Orientation']
export type PostBatch = Schemas['PostBatchIn']
export type ScheduleMode = Schemas['ScheduleMode']
export type SlotsIn = Schemas['SlotsIn']

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: Record<string, unknown>

  constructor(status: number, code: string, message: string, detail: Record<string, unknown>) {
    super(message)
    this.status = status
    this.code = code
    this.detail = detail
  }
}

let csrfToken = ''

export function setCsrfToken(token: string) {
  csrfToken = token
}

type RequestOptions = { method?: string; json?: unknown; form?: FormData }

export async function api<T>(path: string, { method = 'GET', json, form }: RequestOptions = {}) {
  const headers: Record<string, string> = {}
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken
  if (json !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(`/api/v1${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: form ?? (json === undefined ? undefined : JSON.stringify(json)),
    })
  } catch {
    throw new ApiError(
      0,
      'network',
      'Server Schedler nggak bisa dihubungi. Cek apakah backend jalan.',
      {},
    )
  }
  if (res.status === 204) return undefined as T
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw toApiError(res.status, body)
  return body as T
}

function toApiError(status: number, body: unknown): ApiError {
  const err = (
    body as { error?: { code: string; message: string; detail: Record<string, unknown> } }
  )?.error
  if (err) return new ApiError(status, err.code, err.message, err.detail)
  // FastAPI's own 422 (schema validation) has no domain message.
  return new ApiError(status, 'http_' + status, `Permintaan ditolak server (HTTP ${status}).`, {
    body,
  })
}
