<template>
  <main class="store-page">
    <header class="page-header">
      <div>
        <h1>{{ t('Настройки на магазина', 'Store settings') }}</h1>
        <p>
          {{
            t(
              'Общите настройки важат за целия магазин, а публичното съдържание се пази отделно за всеки инсталиран език.',
              'Global settings apply to the whole Store, while public content is stored separately for each installed language.',
            )
          }}
        </p>
      </div>
    </header>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="message" class="message success" role="status">{{ message }}</p>

    <section class="panel">
      <div class="section-header">
        <div>
          <h2>{{ t('Общи настройки', 'Global settings') }}</h2>
          <p>
            {{
              t(
                'Тези стойности не зависят от езика.',
                'These values are language-independent.',
              )
            }}
          </p>
        </div>
      </div>

      <div class="global-grid">
        <label>
          <span>{{ t('Валута', 'Currency') }}</span>
          <input
            v-model.trim="globalForm.currency"
            maxlength="3"
            autocomplete="off"
            placeholder="EUR"
            @input="globalForm.currency = globalForm.currency.toUpperCase()"
          />
          <small>
            {{
              t(
                'Трибуквен ISO код. Смяната на валутата не преизчислява съществуващите цени.',
                'Three-letter ISO code. Changing currency does not convert existing prices.',
              )
            }}
          </small>
        </label>

        <label>
          <span>{{ t('Публичен базов адрес', 'Public base URL') }}</span>
          <input
            v-model.trim="globalForm.public_base_url"
            maxlength="2048"
            inputmode="url"
            placeholder="https://shop.example.com"
          />
          <small>
            {{
              t(
                'Остави празно, докато няма избран публичен origin. Не се приема път, query или credentials.',
                'Leave empty until a public origin is chosen. Paths, queries and credentials are not accepted.',
              )
            }}
          </small>
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <div>
          <h2>{{ t('Публично съдържание', 'Public content') }}</h2>
          <p>
            {{
              t(
                'Езиците идват динамично от активните езикови пакети на 3mm.',
                'Languages are discovered dynamically from active 3mm language packs.',
              )
            }}
          </p>
        </div>
        <span class="language-summary">
          {{ t('Език', 'Language') }}:
          <strong>{{ contentLanguage.toUpperCase() }}</strong>
        </span>
      </div>

      <div class="language-tabs" role="tablist">
        <button
          v-for="code in installedLanguages"
          :key="code"
          type="button"
          class="language-tab"
          :class="{ active: code === contentLanguage }"
          @click="selectContentLanguage(code)"
        >
          {{ code.toUpperCase() }}
          <span v-if="hasUnsavedDraft(code)" class="draft-mark">•</span>
          <span
            v-else-if="hasSavedTranslation(code)"
            class="saved-mark"
          >✓</span>
        </button>
      </div>

      <div class="content-grid">
        <label>
          <span>{{ t('Име на магазина', 'Store name') }}</span>
          <input
            v-model="contentForm.store_name"
            maxlength="160"
          />
        </label>

        <label>
          <span>{{ t('Заглавие на началната страница', 'Home title') }}</span>
          <input
            v-model="contentForm.home_title"
            maxlength="200"
          />
        </label>

        <label class="wide">
          <span>{{ t('Описание на началната страница', 'Home description') }}</span>
          <textarea
            v-model="contentForm.home_description"
            rows="5"
            maxlength="5000"
          />
        </label>

        <label>
          <span>SEO title</span>
          <input
            v-model="contentForm.meta_title"
            maxlength="160"
          />
        </label>

        <label>
          <span>SEO description</span>
          <textarea
            v-model="contentForm.meta_description"
            rows="3"
            maxlength="320"
          />
        </label>
      </div>

      <p class="hint">
        {{
          t(
            'Незаписаните стойности се пазят при превключване между езиците и се записват заедно.',
            'Unsaved values are preserved while switching languages and are saved together.',
          )
        }}
      </p>
    </section>

    <div class="save-bar">
      <div>
        <strong v-if="pendingLanguages.length">
          {{
            t(
              `Незаписани езици: ${pendingLanguages.map(code => code.toUpperCase()).join(', ')}`,
              `Unsaved languages: ${pendingLanguages.map(code => code.toUpperCase()).join(', ')}`,
            )
          }}
        </strong>
        <span v-else>
          {{
            t(
              'Няма незаписани локализирани промени.',
              'No unsaved localized changes.',
            )
          }}
        </span>
      </div>

      <button type="button" :disabled="busy || saving" @click="saveSettings">
        {{
          saving
            ? t('Записване…', 'Saving…')
            : t('Запази настройките', 'Save settings')
        }}
      </button>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import {
  createRequestId,
  invokeApplicationOperation,
  readInstalledLanguages,
} from './application-api'
import { useStoreLanguage } from './language'

interface LocalizedStoreSettings {
  store_name: string
  home_title: string
  home_description: string
  meta_title: string
  meta_description: string
}

interface StoreTranslation extends LocalizedStoreSettings {
  language_code: string
  created_at: string
  updated_at: string
}

interface StoreSettingsSnapshot {
  currency: string
  public_base_url: string
  translations: StoreTranslation[]
}

const { language: uiLanguage, t } = useStoreLanguage()

const installedLanguages = ref<string[]>(['en'])
const contentLanguage = ref('en')
const contentLanguageFollowsUi = ref(true)
const baselineTranslations = ref<Record<string, LocalizedStoreSettings>>({})
const localizedDrafts = ref<Record<string, LocalizedStoreSettings>>({})

const busy = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')

const globalForm = reactive({
  currency: 'EUR',
  public_base_url: '',
})

const contentForm = reactive<LocalizedStoreSettings>({
  store_name: '',
  home_title: '',
  home_description: '',
  meta_title: '',
  meta_description: '',
})

const pendingLanguages = computed(() =>
  Object.keys(localizedDrafts.value).sort(),
)

function token(): string {
  return localStorage.getItem('authToken') || ''
}

async function operation<T>(
  operationId: string,
  payload: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<T> {
  return await invokeApplicationOperation<T>(
    'administrator',
    operationId,
    token(),
    payload,
    idempotencyKey,
  )
}

function blankLocalized(): LocalizedStoreSettings {
  return {
    store_name: '',
    home_title: '',
    home_description: '',
    meta_title: '',
    meta_description: '',
  }
}

function cloneLocalized(
  value: LocalizedStoreSettings,
): LocalizedStoreSettings {
  return {
    store_name: value.store_name,
    home_title: value.home_title,
    home_description: value.home_description,
    meta_title: value.meta_title,
    meta_description: value.meta_description,
  }
}

function currentLocalized(): LocalizedStoreSettings {
  return {
    store_name: contentForm.store_name,
    home_title: contentForm.home_title,
    home_description: contentForm.home_description,
    meta_title: contentForm.meta_title,
    meta_description: contentForm.meta_description,
  }
}

function sameLocalized(
  left: LocalizedStoreSettings,
  right: LocalizedStoreSettings,
): boolean {
  return (
    left.store_name === right.store_name &&
    left.home_title === right.home_title &&
    left.home_description === right.home_description &&
    left.meta_title === right.meta_title &&
    left.meta_description === right.meta_description
  )
}

function baselineForLanguage(code: string): LocalizedStoreSettings {
  return cloneLocalized(
    baselineTranslations.value[code] || blankLocalized(),
  )
}

function applyLocalized(value: LocalizedStoreSettings) {
  contentForm.store_name = value.store_name
  contentForm.home_title = value.home_title
  contentForm.home_description = value.home_description
  contentForm.meta_title = value.meta_title
  contentForm.meta_description = value.meta_description
}

function snapshotLocalizedDraft(code: string) {
  if (!code) return

  const current = currentLocalized()
  const baseline = baselineForLanguage(code)
  const next = { ...localizedDrafts.value }

  if (sameLocalized(current, baseline)) {
    delete next[code]
  } else {
    next[code] = cloneLocalized(current)
  }
  localizedDrafts.value = next
}

function hydrateLanguage(code: string) {
  const draft = localizedDrafts.value[code]
  applyLocalized(
    draft ? cloneLocalized(draft) : baselineForLanguage(code),
  )
}

function hasUnsavedDraft(code: string): boolean {
  return Object.prototype.hasOwnProperty.call(
    localizedDrafts.value,
    code,
  )
}

function hasSavedTranslation(code: string): boolean {
  return Object.prototype.hasOwnProperty.call(
    baselineTranslations.value,
    code,
  )
}

function applySnapshot(snapshot: StoreSettingsSnapshot) {
  globalForm.currency = snapshot.currency
  globalForm.public_base_url = snapshot.public_base_url

  const next: Record<string, LocalizedStoreSettings> = {}
  for (const translation of snapshot.translations) {
    next[translation.language_code] = {
      store_name: translation.store_name,
      home_title: translation.home_title,
      home_description: translation.home_description,
      meta_title: translation.meta_title,
      meta_description: translation.meta_description,
    }
  }
  baselineTranslations.value = next
}

async function loadInstalledLanguages() {
  try {
    installedLanguages.value = await readInstalledLanguages(token())
  } catch {
    installedLanguages.value = Array.from(
      new Set([uiLanguage.value, 'en']),
    )
  }

  if (!installedLanguages.value.includes(contentLanguage.value)) {
    contentLanguage.value = installedLanguages.value.includes(uiLanguage.value)
      ? uiLanguage.value
      : installedLanguages.value[0] || 'en'
  }
}

async function loadSettings() {
  busy.value = true
  error.value = ''
  try {
    await loadInstalledLanguages()
    const result = await operation<StoreSettingsSnapshot>(
      'store_settings_get',
      {},
    )
    applySnapshot(result)

    contentLanguage.value = installedLanguages.value.includes(uiLanguage.value)
      ? uiLanguage.value
      : installedLanguages.value[0] || 'en'
    contentLanguageFollowsUi.value = true
    localizedDrafts.value = {}
    hydrateLanguage(contentLanguage.value)
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Настройките не могат да бъдат заредени.',
            'Could not load Store settings.',
          )
  } finally {
    busy.value = false
  }
}

function selectContentLanguage(code: string) {
  if (code === contentLanguage.value) return
  snapshotLocalizedDraft(contentLanguage.value)
  contentLanguageFollowsUi.value = false
  contentLanguage.value = code
  hydrateLanguage(code)
}

async function saveSettings() {
  error.value = ''
  message.value = ''
  saving.value = true

  try {
    snapshotLocalizedDraft(contentLanguage.value)

    const translations = Object.entries(localizedDrafts.value).map(
      ([language_code, value]) => ({
        language_code,
        ...cloneLocalized(value),
      }),
    )

    const payload: Record<string, unknown> = {
      currency: globalForm.currency,
      public_base_url: globalForm.public_base_url,
    }
    if (translations.length) payload.translations = translations

    const result = await operation<StoreSettingsSnapshot>(
      'store_settings_update',
      payload,
      createRequestId(),
    )

    applySnapshot(result)
    localizedDrafts.value = {}
    hydrateLanguage(contentLanguage.value)
    message.value = t(
      'Настройките са записани.',
      'Store settings saved.',
    )
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Настройките не могат да бъдат записани.',
            'Could not save Store settings.',
          )
  } finally {
    saving.value = false
  }
}

watch(uiLanguage, async (newLanguage) => {
  await loadInstalledLanguages()
  if (
    !contentLanguageFollowsUi.value ||
    !installedLanguages.value.includes(newLanguage) ||
    contentLanguage.value === newLanguage
  ) {
    return
  }

  snapshotLocalizedDraft(contentLanguage.value)
  contentLanguage.value = newLanguage
  hydrateLanguage(newLanguage)
})

onMounted(loadSettings)
</script>

<style scoped>
.store-page {
  max-width: 84rem;
  margin: 0 auto;
  padding: 2rem;
  display: grid;
  gap: 1rem;
  color: var(--text-primary);
}

.page-header,
.section-header,
.save-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.page-header p,
.section-header p,
.hint,
small,
.language-summary,
.save-bar span {
  color: var(--text-secondary);
}

.page-header p,
.section-header p {
  margin: 0.25rem 0 0;
}

.panel,
.save-bar {
  border: 1px solid var(--card-border);
  border-radius: var(--border-radius-md);
  padding: 1rem;
  background: var(--card-bg);
  color: var(--text-primary);
}

.global-grid,
.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

label {
  display: grid;
  align-content: start;
  gap: 0.35rem;
}

.wide {
  grid-column: 1 / -1;
}

input,
textarea,
button {
  font: inherit;
}

input,
textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 2.5rem;
  border: 1px solid var(--input-border);
  border-radius: var(--border-radius-sm);
  padding: 0.55rem 0.7rem;
  background: var(--input-bg);
  color: var(--text-primary);
}

textarea {
  resize: vertical;
}

button {
  min-height: 2.5rem;
  border: 1px solid transparent;
  border-radius: var(--border-radius-sm);
  padding: 0.55rem 0.85rem;
  cursor: pointer;
  background: var(--button-primary-bg);
  color: var(--button-primary-text);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.language-tabs {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 1rem;
}

.language-tab {
  background: var(--card-bg);
  color: var(--text-primary);
  border-color: var(--card-border);
}

.language-tab.active {
  border-color: var(--button-primary-bg);
  box-shadow: inset 0 0 0 1px var(--button-primary-bg);
}

.draft-mark {
  color: var(--warning-color);
  font-size: 1.2rem;
}

.saved-mark {
  color: var(--success-color);
}

.hint {
  margin: 1rem 0 0;
}

.message {
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: var(--border-radius-sm);
  background: var(--card-bg);
}

.message.error {
  border: 1px solid var(--error-color);
  color: var(--error-color);
}

.message.success {
  border: 1px solid var(--success-color);
  color: var(--success-color);
}

@media (max-width: 760px) {
  .store-page {
    padding: 1rem;
  }

  .page-header,
  .section-header,
  .save-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .global-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .wide {
    grid-column: auto;
  }
}
</style>
