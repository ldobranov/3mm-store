<template>
  <section class="products-shell">
    <header class="section-header">
      <div>
        <h2>{{ t('Продукти', 'Products') }}</h2>
        <p>
          {{
            t(
              'Продуктовите данни са общи, а съдържанието се пази отделно по език.',
              'Product data is shared while content is stored separately per language.',
            )
          }}
        </p>
      </div>
      <button type="button" class="secondary" @click="startCreate">
        {{ t('Нов продукт', 'New product') }}
      </button>
    </header>

    <div class="panel filters">
      <label>
        <span>{{ t('Език на съдържанието', 'Content language') }}</span>
        <select :value="contentLanguage" @change="changeListLanguage">
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
          :placeholder="t('Име, SKU или slug', 'Name, SKU or slug')"
          @keyup.enter="reloadFromStart"
        />
      </label>

      <label>
        <span>{{ t('Състояние', 'Status') }}</span>
        <select v-model="statusFilter" @change="reloadFromStart">
          <option value="">{{ t('Всички', 'All') }}</option>
          <option value="draft">{{ t('Чернова', 'Draft') }}</option>
          <option value="active">{{ t('Активни', 'Active') }}</option>
          <option value="archived">{{ t('Архивирани', 'Archived') }}</option>
        </select>
      </label>

      <label>
        <span>{{ t('Подреждане', 'Sort') }}</span>
        <select v-model="sort" @change="reloadFromStart">
          <option value="updated_desc">
            {{ t('Последно променени', 'Recently updated') }}
          </option>
          <option value="name_asc">{{ t('Име A–Z', 'Name A–Z') }}</option>
          <option value="name_desc">{{ t('Име Z–A', 'Name Z–A') }}</option>
          <option value="sku_asc">SKU A–Z</option>
        </select>
      </label>

      <button type="button" @click="reloadFromStart" :disabled="busy">
        {{ t('Приложи', 'Apply') }}
      </button>
    </div>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="message" class="message success" role="status">{{ message }}</p>

    <section v-if="editing" class="panel editor">
      <div class="section-header">
        <div>
          <h3>
            {{
              form.product_id
                ? t('Редакция на продукт', 'Edit product')
                : t('Нов продукт', 'New product')
            }}
          </h3>
          <p>
            {{
              t(
                'SKU, slug, цена, категории и наличност са общи за всички езици.',
                'SKU, slug, price, categories and inventory tracking are shared across languages.',
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

      <div class="form-grid">
        <label>
          <span>SKU</span>
          <input v-model.trim="form.sku" maxlength="80" />
        </label>

        <label>
          <span>Slug</span>
          <input v-model.trim="form.slug" maxlength="120" />
        </label>

        <label>
          <span>{{ t('Цена · minor units', 'Price · minor units') }}</span>
          <input
            v-model.number="form.price_minor"
            type="number"
            min="0"
            max="999999999999"
          />
        </label>

        <label class="checkbox-label">
          <input v-model="form.track_inventory" type="checkbox" />
          <span>{{ t('Следи наличност', 'Track inventory') }}</span>
        </label>

        <label class="wide">
          <span>{{ t('Категории', 'Categories') }}</span>
          <select v-model="form.category_ids" multiple size="5">
            <option
              v-for="category in categoryOptions"
              :key="category.category_id"
              :value="category.category_id"
            >
              {{ category.name }} · {{ category.slug }}
            </option>
          </select>
        </label>

        <label>
          <span>
            {{ t('Име', 'Name') }} · {{ contentLanguage.toUpperCase() }}
          </span>
          <input v-model.trim="form.name" maxlength="200" />
        </label>

        <label>
          <span>
            {{ t('Кратко описание', 'Short description') }}
            · {{ contentLanguage.toUpperCase() }}
          </span>
          <textarea
            v-model.trim="form.short_description"
            rows="3"
            maxlength="500"
          />
        </label>

        <label class="wide">
          <span>
            {{ t('Описание', 'Description') }}
            · {{ contentLanguage.toUpperCase() }}
          </span>
          <textarea
            v-model.trim="form.description"
            rows="7"
            maxlength="10000"
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
        <button type="button" @click="saveProduct" :disabled="saving">
          {{
            saving
              ? t('Записване…', 'Saving…')
              : t('Запази езика и продукта', 'Save language and product')
          }}
        </button>
        <button type="button" class="secondary" @click="cancelEdit">
          {{ t('Отказ', 'Cancel') }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <h3>{{ t('Продукти', 'Products') }}</h3>
        <span>
          {{ total }} {{ t('общо', 'total') }}
          · {{ contentLanguage.toUpperCase() }}
        </span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{{ t('Име', 'Name') }}</th>
              <th>SKU</th>
              <th>Slug</th>
              <th>{{ t('Цена', 'Price') }}</th>
              <th>{{ t('Състояние', 'Status') }}</th>
              <th class="actions-column">{{ t('Действия', 'Actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!busy && products.length === 0">
              <td colspan="6" class="empty">
                {{ t('Няма намерени продукти.', 'No products found.') }}
              </td>
            </tr>
            <tr v-for="product in products" :key="product.product_id">
              <td>{{ product.name }}</td>
              <td><code>{{ product.sku }}</code></td>
              <td><code>{{ product.slug }}</code></td>
              <td>{{ product.price_minor }}</td>
              <td>
                <span class="status" :class="product.status">
                  {{ statusLabel(product.status) }}
                </span>
              </td>
              <td>
                <div class="row-actions">
                  <button
                    type="button"
                    class="secondary"
                    @click="startEdit(product)"
                  >
                    {{ t('Редакция', 'Edit') }}
                  </button>
                  <select
                    class="status-select"
                    :value="product.status"
                    :disabled="saving"
                    @change="changeStatus(product, $event)"
                  >
                    <option value="draft">{{ t('Чернова', 'Draft') }}</option>
                    <option value="active">{{ t('Активен', 'Active') }}</option>
                    <option value="archived">
                      {{ t('Архивиран', 'Archived') }}
                    </option>
                  </select>
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import {
  createRequestId,
  invokeApplicationOperation,
  readInstalledLanguages,
} from './application-api'
import { useStoreLanguage } from './language'

type ProductStatus = 'draft' | 'active' | 'archived'

interface Product {
  product_id: string
  sku: string
  slug: string
  name: string
  short_description: string
  description: string
  status: ProductStatus
  price_minor: number
  track_inventory: boolean
  created_at: string
  updated_at: string
}

interface ProductTranslation {
  language_code: string
  name: string
  short_description: string
  description: string
  meta_title: string
  meta_description: string
  created_at: string
  updated_at: string
}

interface ProductList {
  items: Product[]
  total: number
  limit: number
  offset: number
}

interface ProductDetail {
  product: Product
  legacy_language_code: string | null
  translations: ProductTranslation[]
  category_ids: string[]
}

interface Category {
  category_id: string
  slug: string
  name: string
  status: 'active' | 'archived'
}

interface CategoryList {
  items: Category[]
  total: number
  limit: number
  offset: number
}

interface LocalizedProductDraft {
  name: string
  short_description: string
  description: string
  meta_title: string
  meta_description: string
}

const { language: uiLanguage, t } = useStoreLanguage()

const products = ref<Product[]>([])
const categoryOptions = ref<Category[]>([])
const installedLanguages = ref<string[]>(['en'])
const contentLanguage = ref('en')
const contentLanguageFollowsUi = ref(true)
const translations = ref<Record<string, ProductTranslation>>({})
const localizedDrafts = ref<Record<string, LocalizedProductDraft>>({})
const legacyProduct = ref<Product | null>(null)
const legacySeedLanguage = ref<string | null>(null)

const total = ref(0)
const limit = 20
const offset = ref(0)
const search = ref('')
const statusFilter = ref<'' | ProductStatus>('')
const sort = ref<'name_asc' | 'name_desc' | 'updated_desc' | 'sku_asc'>(
  'updated_desc',
)
const busy = ref(false)
const saving = ref(false)
const editing = ref(false)
const error = ref('')
const message = ref('')

const form = reactive({
  product_id: '',
  sku: '',
  slug: '',
  price_minor: 0,
  track_inventory: true,
  category_ids: [] as string[],
  name: '',
  short_description: '',
  description: '',
  meta_title: '',
  meta_description: '',
})

const pageStart = computed(() =>
  total.value === 0 ? 0 : offset.value + 1,
)
const pageEnd = computed(() =>
  Math.min(offset.value + products.value.length, total.value),
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
  form.short_description = ''
  form.description = ''
  form.meta_title = ''
  form.meta_description = ''
}

function localizedSnapshot(): LocalizedProductDraft {
  return {
    name: form.name,
    short_description: form.short_description,
    description: form.description,
    meta_title: form.meta_title,
    meta_description: form.meta_description,
  }
}

function baselineForLanguage(code: string): LocalizedProductDraft {
  const stored = translations.value[code]
  if (stored) {
    return {
      name: stored.name,
      short_description: stored.short_description,
      description: stored.description,
      meta_title: stored.meta_title,
      meta_description: stored.meta_description,
    }
  }

  if (code === legacySeedLanguage.value && legacyProduct.value) {
    return {
      name: legacyProduct.value.name,
      short_description: legacyProduct.value.short_description,
      description: legacyProduct.value.description,
      meta_title: '',
      meta_description: '',
    }
  }

  return {
    name: '',
    short_description: '',
    description: '',
    meta_title: '',
    meta_description: '',
  }
}

function snapshotLocalizedDraft(code: string) {
  localizedDrafts.value = {
    ...localizedDrafts.value,
    [code]: localizedSnapshot(),
  }
}

function hasUnsavedDraft(code: string): boolean {
  const draft = localizedDrafts.value[code]
  if (!draft) return false
  const baseline = baselineForLanguage(code)
  return Object.keys(baseline).some(
    (key) =>
      draft[key as keyof LocalizedProductDraft] !==
      baseline[key as keyof LocalizedProductDraft],
  )
}

function applyLanguageToForm(code: string) {
  const draft = localizedDrafts.value[code]
  if (draft) {
    Object.assign(form, draft)
    return
  }

  const stored = translations.value[code]
  if (stored) {
    form.name = stored.name
    form.short_description = stored.short_description
    form.description = stored.description
    form.meta_title = stored.meta_title
    form.meta_description = stored.meta_description
    return
  }

  if (code === legacySeedLanguage.value && legacyProduct.value) {
    form.name = legacyProduct.value.name
    form.short_description = legacyProduct.value.short_description
    form.description = legacyProduct.value.description
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

async function loadCategoryOptions() {
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

  categoryOptions.value = collected
}

async function loadProducts() {
  busy.value = true
  error.value = ''
  try {
    const payload: Record<string, unknown> = {
      language_code: contentLanguage.value,
      sort: sort.value,
      limit,
      offset: offset.value,
    }
    if (search.value) payload.search = search.value
    if (statusFilter.value) payload.status = statusFilter.value

    const result = await operation<ProductList>(
      'catalog_list_products',
      payload,
    )
    products.value = result.items
    total.value = result.total
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Продуктите не могат да бъдат заредени.',
            'Could not load products.',
          )
  } finally {
    busy.value = false
  }
}

async function loadProductDetail(productId: string) {
  const detail = await operation<ProductDetail>(
    'catalog_get_product',
    { product_id: productId },
  )

  translations.value = Object.fromEntries(
    detail.translations.map((translation) => [
      translation.language_code,
      translation,
    ]),
  )
  legacyProduct.value = detail.product
  legacySeedLanguage.value =
    detail.legacy_language_code ||
    (detail.translations.length === 0
      ? contentLanguage.value
      : null)

  form.product_id = detail.product.product_id
  form.sku = detail.product.sku
  form.slug = detail.product.slug
  form.price_minor = detail.product.price_minor
  form.track_inventory = detail.product.track_inventory
  form.category_ids = [...detail.category_ids]
  applyLanguageToForm(contentLanguage.value)
}

function clearNotice() {
  error.value = ''
  message.value = ''
}

function startCreate() {
  clearNotice()
  form.product_id = ''
  form.sku = ''
  form.slug = ''
  form.price_minor = 0
  form.track_inventory = true
  form.category_ids = []
  translations.value = {}
  localizedDrafts.value = {}
  legacyProduct.value = null
  legacySeedLanguage.value = null
  clearLocalizedForm()
  editing.value = true
}

async function startEdit(product: Product) {
  clearNotice()
  localizedDrafts.value = {}
  editing.value = true
  saving.value = true
  try {
    await loadProductDetail(product.product_id)
  } catch (reason) {
    editing.value = false
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Продуктът не може да бъде зареден.',
            'Could not load product.',
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
  if (editing.value) snapshotLocalizedDraft(contentLanguage.value)
  contentLanguageFollowsUi.value = false
  contentLanguage.value = code
  applyLanguageToForm(code)
}

async function changeListLanguage(event: Event) {
  const target = event.target as HTMLSelectElement
  const code = target.value
  if (code === contentLanguage.value) return

  if (editing.value) snapshotLocalizedDraft(contentLanguage.value)
  contentLanguageFollowsUi.value = false
  contentLanguage.value = code
  if (editing.value) applyLanguageToForm(code)

  offset.value = 0
  await Promise.all([loadProducts(), loadCategoryOptions()])
}

async function saveProduct() {
  clearNotice()
  if (!form.name || !form.sku || !form.slug) {
    error.value = t(
      'Име, SKU и slug са задължителни.',
      'Name, SKU and slug are required.',
    )
    return
  }

  saving.value = true
  try {
    const content = {
      language_code: contentLanguage.value,
      name: form.name,
      short_description: form.short_description,
      description: form.description,
      meta_title: form.meta_title,
      meta_description: form.meta_description,
    }
    const payload: Record<string, unknown> = {
      sku: form.sku,
      slug: form.slug,
      price_minor: Number(form.price_minor),
      track_inventory: Boolean(form.track_inventory),
      category_ids: [...form.category_ids],
      content,
    }

    let operationId = 'product_create'
    if (form.product_id) {
      operationId = 'product_update'
      payload.product_id = form.product_id
    }

    const result = await operation<{ product: Product }>(
      operationId,
      payload,
      createRequestId(),
    )

    const productId = form.product_id || result.product.product_id
    const savedLanguage = contentLanguage.value
    const remainingDrafts = { ...localizedDrafts.value }
    delete remainingDrafts[savedLanguage]
    localizedDrafts.value = remainingDrafts

    message.value = form.product_id
      ? t('Продуктът е обновен.', 'Product updated.')
      : t('Продуктът е създаден като чернова.', 'Product created as draft.')

    await loadProductDetail(productId)
    await loadProducts()
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Продуктът не може да бъде записан.',
            'Could not save product.',
          )
  } finally {
    saving.value = false
  }
}

async function changeStatus(product: Product, event: Event) {
  const target = event.target as HTMLSelectElement
  const status = target.value as ProductStatus
  if (status === product.status) return

  clearNotice()
  saving.value = true
  try {
    await operation(
      'product_set_status',
      {
        product_id: product.product_id,
        status,
      },
      createRequestId(),
    )
    message.value = t(
      'Състоянието на продукта е променено.',
      'Product status updated.',
    )
    await loadProducts()
  } catch (reason) {
    target.value = product.status
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Състоянието на продукта не може да бъде променено.',
            'Could not change product status.',
          )
  } finally {
    saving.value = false
  }
}

function statusLabel(status: ProductStatus): string {
  if (status === 'active') return t('Активен', 'Active')
  if (status === 'archived') return t('Архивиран', 'Archived')
  return t('Чернова', 'Draft')
}

async function reloadFromStart() {
  offset.value = 0
  await loadProducts()
}

async function previousPage() {
  offset.value = Math.max(0, offset.value - limit)
  await loadProducts()
}

async function nextPage() {
  if (offset.value + limit >= total.value) return
  offset.value += limit
  await loadProducts()
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

  if (editing.value) snapshotLocalizedDraft(contentLanguage.value)
  contentLanguage.value = newLanguage
  offset.value = 0
  if (editing.value) applyLanguageToForm(newLanguage)
  await Promise.all([loadProducts(), loadCategoryOptions()])
})

onMounted(async () => {
  contentLanguage.value = uiLanguage.value
  contentLanguageFollowsUi.value = true
  await loadInstalledLanguages()
  await Promise.all([loadProducts(), loadCategoryOptions()])
})
</script>

<style scoped>
.products-shell {
  display: grid;
  gap: 1rem;
  margin-bottom: 2rem;
}

.section-header,
.actions,
.row-actions,
.pager,
.filters,
.language-tabs {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.section-header,
.pager {
  justify-content: space-between;
}

.section-header p {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
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

select[multiple] {
  min-height: 8rem;
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
  flex-wrap: wrap;
  margin: 0.75rem 0 1rem;
}

.language-tab.active {
  background: var(--button-primary-bg);
  color: var(--button-primary-text);
  border-color: var(--button-primary-bg);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.9rem;
}

.wide {
  grid-column: 1 / -1;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  align-self: end;
  min-height: 2.5rem;
}

.checkbox-label input {
  min-height: auto;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 0.7rem;
  border-bottom: 1px solid var(--card-border);
  text-align: left;
  vertical-align: middle;
}

th,
.pager {
  color: var(--text-secondary);
}

.actions-column {
  width: 1%;
  white-space: nowrap;
}

.status {
  display: inline-block;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}

.status.active {
  color: var(--success-color);
}

.status.archived {
  color: var(--text-muted);
}

.status.draft {
  color: var(--text-secondary);
}

.status-select {
  min-width: 7.5rem;
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
