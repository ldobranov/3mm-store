import { computed, readonly, ref } from 'vue'

export type StoreLanguage = 'bg' | 'en'

const LANGUAGE_KEY = 'preferredLanguage'

function normalizeLanguage(value: unknown): StoreLanguage {
  return value === 'bg' ? 'bg' : 'en'
}

function readLanguage(): StoreLanguage {
  if (typeof window === 'undefined') return 'en'
  return normalizeLanguage(window.localStorage.getItem(LANGUAGE_KEY))
}

const selectedLanguage = ref<StoreLanguage>(readLanguage())

if (typeof window !== 'undefined') {
  window.addEventListener('language-changed', (event) => {
    const detail = event instanceof CustomEvent ? event.detail : null
    selectedLanguage.value = detail?.language
      ? normalizeLanguage(detail.language)
      : readLanguage()
  })
  window.addEventListener('storage', (event) => {
    if (event.key === LANGUAGE_KEY) selectedLanguage.value = readLanguage()
  })
}

export function getStoreLanguage(): StoreLanguage {
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
