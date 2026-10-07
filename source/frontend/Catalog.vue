<template>
  <main class="store-page">
    <header class="page-header">
      <div>
        <h1>{{ t('Каталог на магазина', 'Store catalog') }}</h1>
        <p>
          {{
            t(
              'Управление на категориите. Продуктите идват в следващата стъпка на S1.',
              'Manage Store categories. Products arrive in the next S1 increment.',
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
        <h2>
          {{
            form.category_id
              ? t('Редакция на категория', 'Edit category')
              : t('Нова категория', 'New category')
          }}
        </h2>
        <button type="button" class="secondary" @click="cancelEdit">
          {{ t('Затвори', 'Close') }}
        </button>
      </div>

      <div class="form-grid">
        <label>
          <span>{{ t('Име', 'Name') }}</span>
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
          <span>{{ t('Описание', 'Description') }}</span>
          <textarea
            v-model.trim="form.description"
            rows="4"
            maxlength="5000"
          />
        </label>
      </div>

      <div class="actions">
        <button type="button" @click="saveCategory" :disabled="saving">
          {{
            saving
              ? t('Записване…', 'Saving…')
              : t('Запази категорията', 'Save category')
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
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createRequestId,
  invokeApplicationOperation,
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

interface CategoryList {
  items: Category[]
  total: number
  limit: number
  offset: number
}

const { t } = useStoreLanguage()

const categories = ref<Category[]>([])
const allCategories = ref<Category[]>([])
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

async function loadAllCategories() {
  const collected: Category[] = []
  let cursor = 0
  let expected = 0

  do {
    const result = await operation<CategoryList>(
      'catalog_list_categories',
      { limit: 100, offset: cursor },
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

function clearNotice() {
  error.value = ''
  message.value = ''
}

function startCreate() {
  clearNotice()
  form.category_id = ''
  form.name = ''
  form.slug = ''
  form.description = ''
  form.parent_id = ''
  form.sort_order = 0
  editing.value = true
}

function startEdit(category: Category) {
  clearNotice()
  form.category_id = category.category_id
  form.name = category.name
  form.slug = category.slug
  form.description = category.description
  form.parent_id = category.parent_id || ''
  form.sort_order = category.sort_order
  editing.value = true
}

function cancelEdit() {
  editing.value = false
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
    const payload: Record<string, unknown> = {
      name: form.name,
      slug: form.slug,
      description: form.description,
      parent_id: form.parent_id || null,
      sort_order: Number(form.sort_order),
    }

    let operationId = 'category_create'
    if (form.category_id) {
      operationId = 'category_update'
      payload.category_id = form.category_id
    }

    await operation(
      operationId,
      payload,
      createRequestId(),
    )

    message.value = form.category_id
      ? t('Категорията е обновена.', 'Category updated.')
      : t('Категорията е създадена.', 'Category created.')
    editing.value = false
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

onMounted(async () => {
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
.store-page .pager {
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

button.secondary {
  background: var(--card-bg);
  color: var(--text-primary);
  border-color: var(--card-border);
}

button.secondary:hover:not(:disabled) {
  background: var(--panel-bg);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
