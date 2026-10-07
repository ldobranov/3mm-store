import {
  getStoreLanguage,
  normalizeLanguageCode,
} from './language'

const MODULE_ID = 'org.3mm.store'

type ApplicationAudience = 'operator' | 'administrator'

type RuntimeConfiguration = {
  backend_url?: unknown
  backend_port?: unknown
}

let backendBasePromise: Promise<string> | null = null

function validatedOrigin(value: string): string {
  const parsed = new URL(value)
  if (
    !['http:', 'https:'].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error(responseMessage('configuration'))
  }
  return parsed.origin
}

async function resolveBackendBase(): Promise<string> {
  const response = await fetch('/runtime-config.json', { cache: 'no-store' })
  if (!response.ok) throw new Error(responseMessage('configuration'))

  const configuration = (await response.json()) as RuntimeConfiguration

  if (
    typeof configuration.backend_url === 'string' &&
    configuration.backend_url.trim()
  ) {
    return validatedOrigin(configuration.backend_url.trim())
  }

  if (
    Number.isInteger(configuration.backend_port) &&
    Number(configuration.backend_port) > 0 &&
    Number(configuration.backend_port) <= 65535
  ) {
    return validatedOrigin(
      `${window.location.protocol}//${window.location.hostname}:${configuration.backend_port}`,
    )
  }

  throw new Error(responseMessage('configuration'))
}

export async function getBackendBase(): Promise<string> {
  if (!backendBasePromise) {
    backendBasePromise = resolveBackendBase().catch((reason) => {
      backendBasePromise = null
      throw reason
    })
  }
  return backendBasePromise
}

function responseMessage(status: number | 'configuration'): string {
  const bg = getStoreLanguage() === 'bg'
  if (status === 'configuration') {
    return bg
      ? 'Backend конфигурацията на 3mm не е налична.'
      : 'The 3mm backend configuration is unavailable.'
  }
  if (status === 401 || status === 403) {
    return bg
      ? 'Нямате достъп до тази операция.'
      : 'You do not have access to this operation.'
  }
  if (status === 404) {
    return bg
      ? 'Операцията не е налична в активната версия.'
      : 'The operation is unavailable in the active version.'
  }
  if (status === 409 || status === 422) {
    return bg
      ? 'Данните са променени или не са валидни.'
      : 'The data has changed or is invalid.'
  }
  if (status >= 500) {
    return bg
      ? 'Услугата временно не може да изпълни операцията.'
      : 'The service is temporarily unavailable.'
  }
  return bg ? 'Операцията не беше изпълнена.' : 'The operation failed.'
}

export async function readInstalledLanguages(
  token: string,
): Promise<string[]> {
  const backendBase = await getBackendBase()
  const response = await fetch(`${backendBase}/language/available`, {
    headers: token
      ? { Authorization: `Bearer ${token}` }
      : undefined,
  })

  if (!response.ok) {
    throw new Error(responseMessage(response.status))
  }

  const body = (await response.json()) as { languages?: unknown }
  const values = Array.isArray(body.languages) ? body.languages : []
  const languages = values
    .filter((value): value is string => typeof value === 'string')
    .map(normalizeLanguageCode)

  if (!languages.includes('en')) languages.unshift('en')
  return Array.from(new Set(languages))
}

export function createRequestId(): string {
  const availableCrypto = globalThis.crypto
  if (
    availableCrypto &&
    typeof availableCrypto.randomUUID === 'function'
  ) {
    return availableCrypto.randomUUID()
  }

  const bytes = new Uint8Array(16)
  if (
    availableCrypto &&
    typeof availableCrypto.getRandomValues === 'function'
  ) {
    availableCrypto.getRandomValues(bytes)
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256)
    }
  }

  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(
    bytes,
    (value) => value.toString(16).padStart(2, '0'),
  ).join('')

  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export async function invokeApplicationOperation<T>(
  audience: ApplicationAudience,
  operation: string,
  token: string,
  payload: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<T> {
  const backendBase = await getBackendBase()
  const audiencePath =
    audience === 'administrator' ? '' : `/${audience}`

  const response = await fetch(
    `${backendBase}/api/v1/application-extensions/${MODULE_ID}${audiencePath}/operations/${operation}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        payload,
        ...(idempotencyKey
          ? { idempotency_key: idempotencyKey }
          : {}),
      }),
    },
  )

  if (!response.ok) {
    throw Object.assign(
      new Error(responseMessage(response.status)),
      { httpStatus: response.status },
    )
  }

  return (await response.json()) as T
}
