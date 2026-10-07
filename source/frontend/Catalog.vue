<template>
  <main class="store-catalog-page">
    <header class="page-header">
      <div>
        <h1>Store catalog</h1>
        <p>Manage Store categories. Products arrive in the next S1 increment.</p>
      </div>
      <button type="button" class="secondary" @click="startCreate">
        New category
      </button>
    </header>

    <section class="panel filters">
      <label>
        Search
        <input
          v-model.trim="search"
          maxlength="120"
          placeholder="Name or slug"
          @keyup.enter="reloadFromStart"
        />
      </label>

      <label>
        Status
        <select v-model="statusFilter" @change="reloadFromStart">
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="archived">Archived</option>
        </select>
      </label>

      <button type="button" @click="reloadFromStart" :disabled="busy">
        Apply
      </button>
    </section>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="message" class="message success" role="status">{{ message }}</p>

    <section v-if="editing" class="panel editor">
      <div class="section-header">
        <h2>{{ form.category_id ? 'Edit category' : 'New category' }}</h2>
        <button type="button" class="secondary" @click="cancelEdit">
          Close
        </button>
      </div>

      <div class="form-grid">
        <label>
          Name
          <input v-model.trim="form.name" maxlength="160" />
        </label>

        <label>
          Slug
          <input
            v-model.trim="form.slug"
            maxlength="120"
            placeholder="adult-diapers"
          />
        </label>

        <label>
          Parent
          <select v-model="form.parent_id">
            <option value="">Root category</option>
            <option
              v-for="category in parentOptions"
              :key="category.category_id"
              :value="category.category_id"
            >
              {{ category.name }}
              {{ category.status === 'archived' ? '(archived)' : '' }}
            </option>
          </select>
        </label>

        <label>
          Sort order
          <input
            v-model.number="form.sort_order"
            type="number"
            min="0"
            max="100000"
          />
        </label>

        <label class="wide">
          Description
          <textarea
            v-model.trim="form.description"
            rows="4"
            maxlength="5000"
          />
        </label>
      </div>

      <div class="actions">
        <button type="button" @click="saveCategory" :disabled="saving">
          {{ saving ? 'Saving…' : 'Save category' }}
        </button>
        <button type="button" class="secondary" @click="cancelEdit">
          Cancel
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <h2>Categories</h2>
        <span>{{ total }} total</span>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Parent</th>
              <th>Status</th>
              <th>Order</th>
              <th class="actions-column">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!busy && categories.length === 0">
              <td colspan="6" class="empty">No categories found.</td>
            </tr>
            <tr v-for="category in categories" :key="category.category_id">
              <td>{{ category.name }}</td>
              <td><code>{{ category.slug }}</code></td>
              <td>{{ parentName(category.parent_id) }}</td>
              <td>
                <span class="status" :class="category.status">
                  {{ category.status }}
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
                    Edit
                  </button>
                  <button
                    type="button"
                    class="secondary"
                    :disabled="saving"
                    @click="toggleStatus(category)"
                  >
                    {{ category.status === 'active' ? 'Archive' : 'Activate' }}
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
          Previous
        </button>
        <span>
          {{ pageStart }}–{{ pageEnd }} of {{ total }}
        </span>
        <button
          type="button"
          class="secondary"
          :disabled="busy || offset + limit >= total"
          @click="nextPage"
        >
          Next
        </button>
      </footer>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

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
    category => category.category_id !== form.category_id,
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

async function operation(
  operationId: string,
  payload: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = { payload }
  if (idempotencyKey) body.idempotency_key = idempotencyKey

  const response = await fetch(
    `/api/v1/application-extensions/org.3mm.store/operator/operations/${operationId}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token()}`,
      },
      body: JSON.stringify(body),
    },
  )

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : 'Store operation failed'
    throw new Error(detail)
  }
  return data
}

async function loadAllCategories() {
  const collected: Category[] = []
  let cursor = 0
  let expected = 0

  do {
    const result = (await operation(
      'catalog_list_categories',
      { limit: 100, offset: cursor },
    )) as unknown as CategoryList
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

    const result = (await operation(
      'catalog_list_categories',
      payload,
    )) as unknown as CategoryList

    categories.value = result.items
    total.value = result.total
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : 'Could not load categories'
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
    error.value = 'Name and slug are required.'
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

    await operation(operationId, payload, crypto.randomUUID())
    message.value = form.category_id
      ? 'Category updated.'
      : 'Category created.'
    editing.value = false
    await Promise.all([loadCategories(), loadAllCategories()])
  } catch (reason) {
    error.value =
      reason instanceof Error ? reason.message : 'Could not save category'
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
      crypto.randomUUID(),
    )
    message.value =
      status === 'active' ? 'Category activated.' : 'Category archived.'
    await Promise.all([loadCategories(), loadAllCategories()])
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : 'Could not change category status'
  } finally {
    saving.value = false
  }
}

function parentName(parentId: string | null): string {
  if (!parentId) return '—'
  return (
    allCategories.value.find(
      category => category.category_id === parentId,
    )?.name || parentId
  )
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
.store-catalog-page {
  max-width: 78rem;
  margin: 0 auto;
  padding: 2rem;
  display: grid;
  gap: 1rem;
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
  border: 1px solid var(--border-color, #d7dbe0);
  border-radius: 0.75rem;
  padding: 1rem;
  background: var(--surface-color, #fff);
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
  min-height: 2.5rem;
  border: 1px solid var(--border-color, #c7cbd1);
  border-radius: 0.5rem;
  padding: 0.55rem 0.7rem;
  background: var(--surface-color, #fff);
  color: inherit;
}

textarea {
  resize: vertical;
}

button {
  min-height: 2.5rem;
  border: 1px solid transparent;
  border-radius: 0.5rem;
  padding: 0.55rem 0.85rem;
  cursor: pointer;
  background: var(--primary-color, #2f6fed);
  color: white;
}

button.secondary {
  background: transparent;
  color: inherit;
  border-color: var(--border-color, #c7cbd1);
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
}

th,
td {
  padding: 0.7rem;
  border-bottom: 1px solid var(--border-color, #e3e6ea);
  text-align: left;
  vertical-align: middle;
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

.status.archived {
  opacity: 0.6;
}

.message {
  margin: 0;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
}

.message.error {
  border: 1px solid #b42318;
}

.message.success {
  border: 1px solid #2e7d32;
}

.empty {
  text-align: center;
  opacity: 0.7;
}

@media (max-width: 720px) {
  .store-catalog-page {
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
}
</style>
