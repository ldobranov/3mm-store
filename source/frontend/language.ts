import { computed, readonly, ref } from 'vue'

const LANGUAGE_KEY = 'preferredLanguage'
const LANGUAGE_CODE = /^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/

export function normalizeLanguageCode(value: unknown): string {
  if (typeof value !== 'string') return 'en'
  const code = value.trim().toLowerCase()
  return LANGUAGE_CODE.test(code) ? code : 'en'
}

function readLanguage(): string {
  if (typeof window === 'undefined') return 'en'
  return normalizeLanguageCode(
    window.localStorage.getItem(LANGUAGE_KEY),
  )
}

const selectedLanguage = ref<string>(readLanguage())

if (typeof window !== 'undefined') {
  window.addEventListener('language-changed', (event) => {
    const detail = event instanceof CustomEvent ? event.detail : null
    selectedLanguage.value = detail?.language
      ? normalizeLanguageCode(detail.language)
      : readLanguage()
  })
  window.addEventListener('storage', (event) => {
    if (event.key === LANGUAGE_KEY) {
      selectedLanguage.value = readLanguage()
    }
  })
}

export function getStoreLanguage(): string {
  return selectedLanguage.value
}

export function useStoreLanguage() {
  const language = readonly(selectedLanguage)
  const locale = computed(() =>
    selectedLanguage.value === 'bg' ? 'bg-BG' : 'en-GB',
  )
  const t = (bg: string, en: string) =>
    selectedLanguage.value === 'bg' ? bg : en

  return { language, locale, t }
}
