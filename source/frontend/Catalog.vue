<template>
  <main class="store-page">
    <header class="page-header">
      <div>
        <h1>{{ t('Каталог на магазина', 'Store catalog') }}</h1>
        <p>
          {{
            t(
              'Категориите се редактират отделно за всеки инсталиран език.',
              'Categories are edited separately for every installed language.',
            )
          }}
        </p>
      </div>
      <button type="button" class="secondary" @click="startCreate">
        {{ t('Нова категория', 'New category') }}
      </button>
    </header>

    <section class="panel filters">
      <label>
        <span>{{ t('Език на съдържанието', 'Content language') }}</span>
        <select
          :value="contentLanguage"
          @change="changeListLanguage"
        >
          <option
            v-for="code in installedLanguages"
            :key="code"
            :value="code"
          >
            {{ code.toUpperCase() }}
          </option>
        </select>
      </label>

      <label>
        <span>{{ t('Търсене', 'Search') }}</span>
        <input
          v-model.trim="search"
          maxlength="120"
          :placeholder="t('Име или slug', 'Name or slug')"
          @keyup.enter="reloadFromStart"
        />
      </label>

      <label>
        <span>{{ t('Състояние', 'Status') }}</span>
        <select v-model="statusFilter" @change="reloadFromStart">
          <option value="">{{ t('Всички', 'All') }}</option>
          <option value="active">{{ t('Активни', 'Active') }}</option>
          <option value="archived">{{ t('Архивирани', 'Archived') }}</option>
        </select>
      </label>

      <button type="button" @click="reloadFromStart" :disabled="busy">
        {{ t('Приложи', 'Apply') }}
      </button>
    </section>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="message" class="message success" role="status">{{ message }}</p>

    <section v-if="editing" class="panel editor">
      <div class="section-header">
        <div>
          <h2>
            {{
              form.category_id
                ? t('Редакция на категория', 'Edit category')
                : t('Нова категория', 'New category')
            }}
          </h2>
          <p class="section-help">
            {{
              t(
                'Slug, родител и ред са общи. Името, описанията и SEO текстовете са по език.',
                'Slug, parent and order are shared. Names, descriptions and SEO text are language-specific.',
              )
            }}
          </p>
        </div>
        <button type="button" class="secondary" @click="cancelEdit">
          {{ t('Затвори', 'Close') }}
        </button>
      </div>

      <div class="language-tabs" role="tablist">
        <button
          v-for="code in installedLanguages"
          :key="code"
          type="button"
          class="language-tab"
          :class="{ active: code === contentLanguage }"
          @click="switchEditorLanguage(code)"
        >
          {{ code.toUpperCase() }}
          <span v-if="hasUnsavedDraft(code)" aria-hidden="true">•</span>
          <span v-else-if="hasStoredTranslation(code)" aria-hidden="true">✓</span>
          <span
            v-else-if="code === legacySeedLanguage"
            aria-hidden="true"
          >~</span>
        </button>
      </div>

      <p
        v-if="
          form.category_id &&
          !hasStoredTranslation(contentLanguage) &&
          contentLanguage === legacySeedLanguage
        "
        class="legacy-note"
      >
        {{
          t(
            'Този текст е от стария едноезичен запис. Записването ще го потвърди за избрания език.',
            'This text comes from the legacy single-language record. Saving will assign it to the selected language.',
          )
        }}
      </p>

      <div class="form-grid">
        <label>
          <span>{{ t('Име', 'Name') }} · {{ contentLanguage.toUpperCase() }}</span>
          <input v-model.trim="form.name" maxlength="160" />
        </label>

        <label>
          <span>Slug</span>
          <input
            v-model.trim="form.slug"
            maxlength="120"
            placeholder="adult-diapers"
          />
        </label>

        <label>
          <span>{{ t('Родителска категория', 'Parent') }}</span>
          <select v-model="form.parent_id">
            <option value="">
              {{ t('Основна категория', 'Root category') }}
            </option>
            <option
              v-for="category in parentOptions"
              :key="category.category_id"
              :value="category.category_id"
            >
              {{ category.name }}
              {{
                category.status === 'archived'
                  ? t('(архивирана)', '(archived)')
                  : ''
              }}
            </option>
          </select>
        </label>

        <label>
          <span>{{ t('Ред', 'Sort order') }}</span>
          <input
            v-model.number="form.sort_order"
            type="number"
            min="0"
            max="100000"
          />
        </label>

        <label class="wide">
          <span>
            {{ t('Описание', 'Description') }}
            · {{ contentLanguage.toUpperCase() }}
          </span>
          <textarea
            v-model.trim="form.description"
            rows="5"
            maxlength="5000"
          />
        </label>

        <label>
          <span>
            {{ t('SEO заглавие', 'SEO title') }}
            · {{ contentLanguage.toUpperCase() }}
          </span>
          <input v-model.trim="form.meta_title" maxlength="160" />
        </label>

        <label>
          <span>
            {{ t('SEO описание', 'SEO description') }}
            · {{ contentLanguage.toUpperCase() }}
          </span>
          <textarea
            v-model.trim="form.meta_description"
            rows="3"
            maxlength="320"
          />
        </label>
      </div>

      <div class="actions">
        <button type="button" @click="saveCategory" :disabled="saving">
          {{
            saving
              ? t('Записване…', 'Saving…')
              : t('Запази езика и категорията', 'Save language and category')
          }}
        </button>
        <button type="button" class="secondary" @click="cancelEdit">
          {{ t('Отказ', 'Cancel') }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <h2>{{ t('Категории', 'Categories') }}</h2>
        <span>
          {{ total }}
          {{ t('общо', 'total') }}
          · {{ contentLanguage.toUpperCase() }}
        </span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('Име', 'Name') }}</th>
              <th>Slug</th>
              <th>{{ t('Родител', 'Parent') }}</th>
              <th>{{ t('Състояние', 'Status') }}</th>
              <th>{{ t('Ред', 'Order') }}</th>
              <th class="actions-column">{{ t('Действия', 'Actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!busy && categories.length === 0">
              <td colspan="6" class="empty">
                {{ t('Няма намерени категории.', 'No categories found.') }}
              </td>
            </tr>
            <tr v-for="category in categories" :key="category.category_id">
              <td>{{ category.name }}</td>
              <td><code>{{ category.slug }}</code></td>
              <td>{{ parentName(category.parent_id) }}</td>
              <td>
                <span class="status" :class="category.status">
                  {{ statusLabel(category.status) }}
                </span>
              </td>
              <td>{{ category.sort_order }}</td>
              <td>
                <div class="row-actions">
                  <button
                    type="button"
                    class="secondary"
                    @click="startEdit(category)"
                  >
                    {{ t('Редакция', 'Edit') }}
                  </button>
                  <button
                    type="button"
                    class="secondary"
                    :disabled="saving"
                    @click="toggleStatus(category)"
                  >
                    {{
                      category.status === 'active'
                        ? t('Архивирай', 'Archive')
                        : t('Активирай', 'Activate')
                    }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="pager">
        <button
          type="button"
          class="secondary"
          :disabled="busy || offset === 0"
          @click="previousPage"
        >
          {{ t('Назад', 'Previous') }}
        </button>
        <span>
          {{ pageStart }}–{{ pageEnd }}
          {{ t('от', 'of') }}
          {{ total }}
        </span>
        <button
          type="button"
          class="secondary"
          :disabled="busy || offset + limit >= total"
          @click="nextPage"
        >
          {{ t('Напред', 'Next') }}
        </button>
      </footer>
    </section>
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

type CategoryStatus = 'active' | 'archived'

interface Category {
  category_id: string
  slug: string
  name: string
  description: string
  parent_id: string | null
  sort_order: number
  status: CategoryStatus
  created_at: string
  updated_at: string
}

interface CategoryTranslation {
  language_code: string
  name: string
  description: string
  meta_title: string
  meta_description: string
  created_at: string
  updated_at: string
}

interface LocalizedCategoryDraft {
  name: string
  description: string
  meta_title: string
  meta_description: string
}

interface CategoryList {
  items: Category[]
  total: number
  limit: number
  offset: number
}

interface CategoryDetail {
  category: Category
  legacy_language_code: string | null
  translations: CategoryTranslation[]
}

const { language: uiLanguage, t } = useStoreLanguage()

const categories = ref<Category[]>([])
const allCategories = ref<Category[]>([])
const installedLanguages = ref<string[]>(['en'])
const contentLanguage = ref('en')
const contentLanguageFollowsUi = ref(true)
const translations = ref<Record<string, CategoryTranslation>>({})
const localizedDrafts = ref<Record<string, LocalizedCategoryDraft>>({})
const legacyCategory = ref<Category | null>(null)
const legacySeedLanguage = ref<string | null>(null)

const total = ref(0)
const limit = 20
const offset = ref(0)
const search = ref('')
const statusFilter = ref<'' | CategoryStatus>('')
const busy = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const editing = ref(false)

const form = reactive({
  category_id: '',
  name: '',
  slug: '',
  description: '',
  meta_title: '',
  meta_description: '',
  parent_id: '',
  sort_order: 0,
})

const parentOptions = computed(() =>
  allCategories.value.filter(
    (category) => category.category_id !== form.category_id,
  ),
)

const pageStart = computed(() =>
  total.value === 0 ? 0 : offset.value + 1,
)
const pageEnd = computed(() =>
  Math.min(offset.value + categories.value.length, total.value),
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
    'operator',
    operationId,
    token(),
    payload,
    idempotencyKey,
  )
}

function clearLocalizedForm() {
  form.name = ''
  form.description = ''
  form.meta_title = ''
  form.meta_description = ''
}

function localizedFormSnapshot(): LocalizedCategoryDraft {
  return {
    name: form.name,
    description: form.description,
    meta_title: form.meta_title,
    meta_description: form.meta_description,
  }
}

function baselineForLanguage(code: string): LocalizedCategoryDraft {
  const stored = translations.value[code]
  if (stored) {
    return {
      name: stored.name,
      description: stored.description,
      meta_title: stored.meta_title,
      meta_description: stored.meta_description,
    }
  }

  if (
    code === legacySeedLanguage.value &&
    legacyCategory.value
  ) {
    return {
      name: legacyCategory.value.name,
      description: legacyCategory.value.description,
      meta_title: '',
      meta_description: '',
    }
  }

  return {
    name: '',
    description: '',
    meta_title: '',
    meta_description: '',
  }
}

function snapshotLocalizedDraft(code: string) {
  localizedDrafts.value = {
    ...localizedDrafts.value,
    [code]: localizedFormSnapshot(),
  }
}

function hasUnsavedDraft(code: string): boolean {
  const draft = localizedDrafts.value[code]
  if (!draft) return false
  const baseline = baselineForLanguage(code)
  return (
    draft.name !== baseline.name ||
    draft.description !== baseline.description ||
    draft.meta_title !== baseline.meta_title ||
    draft.meta_description !== baseline.meta_description
  )
}

function applyLanguageToForm(code: string) {
  const draft = localizedDrafts.value[code]
  if (draft) {
    form.name = draft.name
    form.description = draft.description
    form.meta_title = draft.meta_title
    form.meta_description = draft.meta_description
    return
  }

  const stored = translations.value[code]
  if (stored) {
    form.name = stored.name
    form.description = stored.description
    form.meta_title = stored.meta_title
    form.meta_description = stored.meta_description
    return
  }

  if (
    code === legacySeedLanguage.value &&
    legacyCategory.value
  ) {
    form.name = legacyCategory.value.name
    form.description = legacyCategory.value.description
    form.meta_title = ''
    form.meta_description = ''
    return
  }

  clearLocalizedForm()
}

function hasStoredTranslation(code: string): boolean {
  return Boolean(translations.value[code])
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

async function loadAllCategories() {
  const collected: Category[] = []
  let cursor = 0
  let expected = 0

  do {
    const result = await operation<CategoryList>(
      'catalog_list_categories',
      {
        language_code: contentLanguage.value,
        limit: 100,
        offset: cursor,
      },
    )
    collected.push(...result.items)
    expected = result.total
    cursor += result.items.length
    if (result.items.length === 0) break
  } while (cursor < expected)

  allCategories.value = collected
}

async function loadCategories() {
  busy.value = true
  error.value = ''
  try {
    const payload: Record<string, unknown> = {
      language_code: contentLanguage.value,
      limit,
      offset: offset.value,
    }
    if (search.value) payload.search = search.value
    if (statusFilter.value) payload.status = statusFilter.value

    const result = await operation<CategoryList>(
      'catalog_list_categories',
      payload,
    )

    categories.value = result.items
    total.value = result.total
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Категориите не могат да бъдат заредени.',
            'Could not load categories.',
          )
  } finally {
    busy.value = false
  }
}

async function loadCategoryDetail(categoryId: string) {
  const detail = await operation<CategoryDetail>(
    'catalog_get_category',
    { category_id: categoryId },
  )

  translations.value = Object.fromEntries(
    detail.translations.map((translation) => [
      translation.language_code,
      translation,
    ]),
  )
  legacyCategory.value = detail.category
  legacySeedLanguage.value =
    detail.legacy_language_code ||
    (detail.translations.length === 0
      ? contentLanguage.value
      : null)

  form.category_id = detail.category.category_id
  form.slug = detail.category.slug
  form.parent_id = detail.category.parent_id || ''
  form.sort_order = detail.category.sort_order
  applyLanguageToForm(contentLanguage.value)
}

function clearNotice() {
  error.value = ''
  message.value = ''
}

function startCreate() {
  clearNotice()
  form.category_id = ''
  form.slug = ''
  form.parent_id = ''
  form.sort_order = 0
  translations.value = {}
  localizedDrafts.value = {}
  legacyCategory.value = null
  legacySeedLanguage.value = null
  clearLocalizedForm()
  editing.value = true
}

async function startEdit(category: Category) {
  clearNotice()
  localizedDrafts.value = {}
  editing.value = true
  saving.value = true
  try {
    await loadCategoryDetail(category.category_id)
  } catch (reason) {
    editing.value = false
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Категорията не може да бъде заредена.',
            'Could not load category.',
          )
  } finally {
    saving.value = false
  }
}

function cancelEdit() {
  editing.value = false
  localizedDrafts.value = {}
}

function switchEditorLanguage(code: string) {
  if (code === contentLanguage.value) return
  if (editing.value) {
    snapshotLocalizedDraft(contentLanguage.value)
  }
  contentLanguageFollowsUi.value = false
  contentLanguage.value = code
  applyLanguageToForm(code)
}

async function changeListLanguage(event: Event) {
  const target = event.target as HTMLSelectElement
  const code = target.value
  if (code === contentLanguage.value) return

  if (editing.value) {
    snapshotLocalizedDraft(contentLanguage.value)
  }

  contentLanguageFollowsUi.value = false
  contentLanguage.value = code

  if (editing.value) {
    applyLanguageToForm(code)
  }

  offset.value = 0
  await Promise.all([loadCategories(), loadAllCategories()])
}

async function saveCategory() {
  clearNotice()
  if (!form.name || !form.slug) {
    error.value = t(
      'Името и slug са задължителни.',
      'Name and slug are required.',
    )
    return
  }

  saving.value = true
  try {
    const content = {
      language_code: contentLanguage.value,
      name: form.name,
      description: form.description,
      meta_title: form.meta_title,
      meta_description: form.meta_description,
    }

    const payload: Record<string, unknown> = {
      slug: form.slug,
      parent_id: form.parent_id || null,
      sort_order: Number(form.sort_order),
      content,
    }

    let operationId = 'category_create'
    if (form.category_id) {
      operationId = 'category_update'
      payload.category_id = form.category_id
    }

    const result = await operation<{ category: Category }>(
      operationId,
      payload,
      createRequestId(),
    )

    const categoryId =
      form.category_id || result.category.category_id
    const savedLanguage = contentLanguage.value
    const remainingDrafts = { ...localizedDrafts.value }
    delete remainingDrafts[savedLanguage]
    localizedDrafts.value = remainingDrafts

    message.value = form.category_id
      ? t('Категорията е обновена.', 'Category updated.')
      : t('Категорията е създадена.', 'Category created.')

    await loadCategoryDetail(categoryId)
    await Promise.all([loadCategories(), loadAllCategories()])
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Категорията не може да бъде записана.',
            'Could not save category.',
          )
  } finally {
    saving.value = false
  }
}

async function toggleStatus(category: Category) {
  clearNotice()
  saving.value = true
  try {
    const status: CategoryStatus =
      category.status === 'active' ? 'archived' : 'active'

    await operation(
      'category_set_status',
      {
        category_id: category.category_id,
        status,
      },
      createRequestId(),
    )

    message.value =
      status === 'active'
        ? t('Категорията е активирана.', 'Category activated.')
        : t('Категорията е архивирана.', 'Category archived.')
    await Promise.all([loadCategories(), loadAllCategories()])
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Състоянието на категорията не може да бъде променено.',
            'Could not change category status.',
          )
  } finally {
    saving.value = false
  }
}

function parentName(parentId: string | null): string {
  if (!parentId) return '—'
  return (
    allCategories.value.find(
      (category) => category.category_id === parentId,
    )?.name || parentId
  )
}

function statusLabel(status: CategoryStatus): string {
  return status === 'active'
    ? t('Активна', 'Active')
    : t('Архивирана', 'Archived')
}

async function reloadFromStart() {
  offset.value = 0
  await loadCategories()
}

async function previousPage() {
  offset.value = Math.max(0, offset.value - limit)
  await loadCategories()
}

async function nextPage() {
  if (offset.value + limit >= total.value) return
  offset.value += limit
  await loadCategories()
}

watch(uiLanguage, async (newLanguage) => {
  await loadInstalledLanguages()

  if (
    !contentLanguageFollowsUi.value ||
    !installedLanguages.value.includes(newLanguage)
  ) {
    return
  }

  if (contentLanguage.value === newLanguage) return

  if (editing.value) {
    snapshotLocalizedDraft(contentLanguage.value)
  }

  contentLanguage.value = newLanguage
  offset.value = 0

  if (editing.value) {
    applyLanguageToForm(newLanguage)
  }

  await Promise.all([loadCategories(), loadAllCategories()])
})

onMounted(async () => {
  contentLanguage.value = uiLanguage.value
  contentLanguageFollowsUi.value = true
  await loadInstalledLanguages()
  await Promise.all([loadCategories(), loadAllCategories()])
})
</script>

<style scoped>
.store-page {
  max-width: 78rem;
  margin: 0 auto;
  padding: 2rem;
  display: grid;
  gap: 1rem;
  color: var(--text-primary);
}

.store-page p,
.store-page .section-header > span,
.store-page .pager,
.section-help {
  color: var(--text-secondary);
}

.page-header,
.section-header,
.actions,
.row-actions,
.pager,
.filters {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.page-header,
.section-header,
.pager {
  justify-content: space-between;
}

.panel {
  border: 1px solid var(--card-border);
  border-radius: var(--border-radius-md);
  padding: 1rem;
  background: var(--card-bg);
  color: var(--text-primary);
}

.filters {
  align-items: end;
  flex-wrap: wrap;
}

label {
  display: grid;
  gap: 0.35rem;
  color: var(--text-primary);
}

input,
select,
textarea,
button {
  font: inherit;
}

input,
select,
textarea {
  box-sizing: border-box;
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

button:hover:not(:disabled) {
  background: var(--button-primary-hover);
}

button.secondary,
.language-tab {
  background: var(--card-bg);
  color: var(--text-primary);
  border-color: var(--card-border);
}

button.secondary:hover:not(:disabled),
.language-tab:hover:not(:disabled) {
  background: var(--panel-bg);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.language-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0 1rem;
}

.language-tab {
  min-width: 4.5rem;
}

.language-tab.active {
  background: var(--button-primary-bg);
  color: var(--button-primary-text);
  border-color: var(--button-primary-bg);
}

.legacy-note {
  margin: 0 0 1rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--card-border);
  border-radius: var(--border-radius-sm);
  background: var(--panel-bg);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.wide {
  grid-column: 1 / -1;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  color: var(--text-primary);
}

th,
td {
  padding: 0.7rem;
  border-bottom: 1px solid var(--card-border);
  text-align: left;
  vertical-align: middle;
}

th {
  color: var(--text-secondary);
}

code {
  color: var(--text-primary);
}

.actions-column {
  width: 1%;
  white-space: nowrap;
}

.status {
  display: inline-block;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  border: 1px solid currentColor;
  font-size: 0.85rem;
}

.status.active {
  color: var(--success-color);
}

.status.archived {
  color: var(--text-muted);
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

.empty {
  text-align: center;
  color: var(--text-muted);
}

@media (max-width: 720px) {
  .store-page {
    padding: 1rem;
  }

  .page-header,
  .section-header,
  .pager {
    align-items: stretch;
    flex-direction: column;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .wide {
    grid-column: auto;
  }

  .row-actions {
    flex-wrap: wrap;
  }
}
</style>
