<template>
  <main class="store-page">
    <header class="page-header">
      <div>
        <h1>{{ t('Наличности', 'Store inventory') }}</h1>
        <p>
          {{
            t(
              'Следи текущите количества и прави отчетими корекции на наличността.',
              'Track current quantities and make auditable stock adjustments.',
            )
          }}
        </p>
      </div>
    </header>

    <section class="panel filters">
      <label>
        <span>{{ t('Език на съдържанието', 'Content language') }}</span>
        <select :value="contentLanguage" @change="changeContentLanguage">
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
        <span>{{ t('Състояние на продукта', 'Product status') }}</span>
        <select v-model="statusFilter" @change="reloadFromStart">
          <option value="">{{ t('Всички', 'All') }}</option>
          <option value="draft">{{ t('Чернова', 'Draft') }}</option>
          <option value="active">{{ t('Активни', 'Active') }}</option>
          <option value="archived">{{ t('Архивирани', 'Archived') }}</option>
        </select>
      </label>

      <label>
        <span>{{ t('Наличност', 'Availability') }}</span>
        <select v-model="availabilityFilter" @change="reloadFromStart">
          <option value="">{{ t('Всички', 'All') }}</option>
          <option value="in_stock">{{ t('В наличност', 'In stock') }}</option>
          <option value="out_of_stock">{{ t('Изчерпани', 'Out of stock') }}</option>
          <option value="untracked">{{ t('Без следене', 'Untracked') }}</option>
        </select>
      </label>

      <label>
        <span>{{ t('Подреждане', 'Sort') }}</span>
        <select v-model="sort" @change="reloadFromStart">
          <option value="updated_desc">
            {{ t('Последно променени', 'Recently updated') }}
          </option>
          <option value="name_asc">{{ t('Име A–Z', 'Name A–Z') }}</option>
          <option value="sku_asc">SKU A–Z</option>
          <option value="stock_desc">
            {{ t('Количество ↓', 'Stock ↓') }}
          </option>
          <option value="stock_asc">
            {{ t('Количество ↑', 'Stock ↑') }}
          </option>
        </select>
      </label>

      <button type="button" @click="reloadFromStart" :disabled="busy">
        {{ t('Приложи', 'Apply') }}
      </button>
    </section>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-if="message" class="message success" role="status">{{ message }}</p>

    <section v-if="selectedItem" class="panel editor">
      <div class="section-header">
        <div>
          <h2>{{ t('Корекция на наличност', 'Adjust inventory') }}</h2>
          <p>
            <strong>{{ selectedItem.name }}</strong>
            · <code>{{ selectedItem.sku }}</code>
            · {{ t('текущо', 'current') }}:
            <strong>{{ selectedItem.stock_on_hand }}</strong>
          </p>
        </div>
        <button type="button" class="secondary" @click="closeAdjustment">
          {{ t('Затвори', 'Close') }}
        </button>
      </div>

      <div class="adjustment-grid">
        <label>
          <span>{{ t('Промяна', 'Delta') }}</span>
          <input
            v-model.number="adjustment.delta"
            type="number"
            step="1"
            min="-1000000000"
            max="1000000000"
          />
          <small>
            {{
              t(
                'Положително число добавя, отрицателно изважда.',
                'Positive adds stock; negative removes stock.',
              )
            }}
          </small>
        </label>

        <label>
          <span>{{ t('Причина', 'Reason') }}</span>
          <input
            v-model.trim="adjustment.reason"
            maxlength="240"
            :placeholder="
              t(
                'Напр. доставка, корекция, брак',
                'e.g. delivery, correction, damaged stock',
              )
            "
          />
        </label>
      </div>

      <div class="preview">
        {{ t('Ново количество', 'New stock') }}:
        <strong>{{ projectedStock }}</strong>
      </div>

      <div class="actions">
        <button
          type="button"
          :disabled="saving || !canAdjust"
          @click="applyAdjustment"
        >
          {{
            saving
              ? t('Записване…', 'Saving…')
              : t('Запиши корекцията', 'Apply adjustment')
          }}
        </button>
        <button type="button" class="secondary" @click="closeAdjustment">
          {{ t('Отказ', 'Cancel') }}
        </button>
      </div>
    </section>

    <section class="panel">
      <div class="section-header">
        <h2>{{ t('Продукти и наличности', 'Products and stock') }}</h2>
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
              <th>{{ t('Продукт', 'Product') }}</th>
              <th>{{ t('Следене', 'Tracking') }}</th>
              <th>{{ t('Количество', 'Stock') }}</th>
              <th>{{ t('Наличност', 'Availability') }}</th>
              <th>{{ t('Променено', 'Updated') }}</th>
              <th class="actions-column">{{ t('Действия', 'Actions') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!busy && items.length === 0">
              <td colspan="8" class="empty">
                {{ t('Няма намерени продукти.', 'No products found.') }}
              </td>
            </tr>

            <tr v-for="item in items" :key="item.product_id">
              <td>{{ item.name }}</td>
              <td><code>{{ item.sku }}</code></td>
              <td>
                <span class="status" :class="item.product_status">
                  {{ productStatusLabel(item.product_status) }}
                </span>
              </td>
              <td>
                {{
                  item.track_inventory
                    ? t('Да', 'Yes')
                    : t('Не', 'No')
                }}
              </td>
              <td class="stock-number">{{ item.stock_on_hand }}</td>
              <td>
                <span class="availability" :class="item.availability">
                  {{ availabilityLabel(item.availability) }}
                </span>
              </td>
              <td>{{ formatDate(item.updated_at) }}</td>
              <td>
                <button
                  type="button"
                  class="secondary"
                  @click="openAdjustment(item)"
                >
                  {{ t('Корекция', 'Adjust') }}
                </button>
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

type ProductStatus = 'draft' | 'active' | 'archived'
type Availability = 'in_stock' | 'out_of_stock' | 'untracked'
type InventorySort =
  | 'updated_desc'
  | 'name_asc'
  | 'sku_asc'
  | 'stock_asc'
  | 'stock_desc'

interface InventoryItem {
  product_id: string
  sku: string
  slug: string
  name: string
  product_status: ProductStatus
  track_inventory: boolean
  stock_on_hand: number
  availability: Availability
  updated_at: string
}

interface InventoryList {
  items: InventoryItem[]
  total: number
  limit: number
  offset: number
}

interface AdjustmentResult {
  adjustment: {
    adjustment_id: string
    product_id: string
    delta: number
    stock_before: number
    stock_after: number
    reason: string
    created_at: string
  }
}

const { language: uiLanguage, locale, t } = useStoreLanguage()

const items = ref<InventoryItem[]>([])
const installedLanguages = ref<string[]>(['en'])
const contentLanguage = ref('en')
const contentLanguageFollowsUi = ref(true)
const selectedItem = ref<InventoryItem | null>(null)

const total = ref(0)
const limit = 20
const offset = ref(0)
const search = ref('')
const statusFilter = ref<'' | ProductStatus>('')
const availabilityFilter = ref<'' | Availability>('')
const sort = ref<InventorySort>('updated_desc')
const busy = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')

const adjustment = reactive({
  delta: 0,
  reason: '',
})

const pageStart = computed(() =>
  total.value === 0 ? 0 : offset.value + 1,
)
const pageEnd = computed(() =>
  Math.min(offset.value + items.value.length, total.value),
)
const projectedStock = computed(() =>
  (selectedItem.value?.stock_on_hand || 0) + Number(adjustment.delta || 0),
)
const canAdjust = computed(() =>
  Boolean(
    selectedItem.value &&
      Number.isInteger(Number(adjustment.delta)) &&
      Number(adjustment.delta) !== 0 &&
      projectedStock.value >= 0 &&
      adjustment.reason.trim(),
  ),
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

function clearNotice() {
  error.value = ''
  message.value = ''
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

async function loadInventory() {
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
    if (availabilityFilter.value) {
      payload.availability = availabilityFilter.value
    }

    const result = await operation<InventoryList>(
      'inventory_list',
      payload,
    )
    items.value = result.items
    total.value = result.total
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Наличностите не могат да бъдат заредени.',
            'Could not load inventory.',
          )
  } finally {
    busy.value = false
  }
}

function openAdjustment(item: InventoryItem) {
  clearNotice()
  selectedItem.value = item
  adjustment.delta = 0
  adjustment.reason = ''
}

function closeAdjustment() {
  selectedItem.value = null
  adjustment.delta = 0
  adjustment.reason = ''
}

async function applyAdjustment() {
  if (!selectedItem.value || !canAdjust.value) return

  clearNotice()
  saving.value = true
  try {
    const result = await operation<AdjustmentResult>(
      'inventory_adjust',
      {
        product_id: selectedItem.value.product_id,
        delta: Number(adjustment.delta),
        reason: adjustment.reason,
      },
      createRequestId(),
    )

    message.value = t(
      `Наличността е променена от ${result.adjustment.stock_before} на ${result.adjustment.stock_after}.`,
      `Stock changed from ${result.adjustment.stock_before} to ${result.adjustment.stock_after}.`,
    )
    closeAdjustment()
    await loadInventory()
  } catch (reason) {
    error.value =
      reason instanceof Error
        ? reason.message
        : t(
            'Корекцията на наличността не може да бъде записана.',
            'Could not apply inventory adjustment.',
          )
  } finally {
    saving.value = false
  }
}

async function changeContentLanguage(event: Event) {
  const target = event.target as HTMLSelectElement
  const code = target.value
  if (code === contentLanguage.value) return

  contentLanguageFollowsUi.value = false
  contentLanguage.value = code
  offset.value = 0
  await loadInventory()
}

function productStatusLabel(status: ProductStatus): string {
  if (status === 'active') return t('Активен', 'Active')
  if (status === 'archived') return t('Архивиран', 'Archived')
  return t('Чернова', 'Draft')
}

function availabilityLabel(value: Availability): string {
  if (value === 'in_stock') return t('В наличност', 'In stock')
  if (value === 'out_of_stock') return t('Изчерпан', 'Out of stock')
  return t('Без следене', 'Untracked')
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

async function reloadFromStart() {
  offset.value = 0
  await loadInventory()
}

async function previousPage() {
  offset.value = Math.max(0, offset.value - limit)
  await loadInventory()
}

async function nextPage() {
  if (offset.value + limit >= total.value) return
  offset.value += limit
  await loadInventory()
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

  contentLanguage.value = newLanguage
  offset.value = 0
  await loadInventory()
})

onMounted(async () => {
  contentLanguage.value = uiLanguage.value
  contentLanguageFollowsUi.value = true
  await loadInstalledLanguages()
  await loadInventory()
})
</script>

<style scoped>
.store-page {
  max-width: 92rem;
  margin: 0 auto;
  padding: 2rem;
  display: grid;
  gap: 1rem;
  color: var(--text-primary);
}

.page-header,
.section-header,
.actions,
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

.page-header p,
.section-header p,
.pager,
small {
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
button {
  font: inherit;
}

input,
select {
  box-sizing: border-box;
  min-height: 2.5rem;
  border: 1px solid var(--input-border);
  border-radius: var(--border-radius-sm);
  padding: 0.55rem 0.7rem;
  background: var(--input-bg);
  color: var(--text-primary);
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

.adjustment-grid {
  display: grid;
  grid-template-columns: minmax(12rem, 0.5fr) minmax(18rem, 1.5fr);
  gap: 1rem;
  margin: 1rem 0;
}

.preview {
  margin-bottom: 1rem;
  color: var(--text-secondary);
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

th {
  color: var(--text-secondary);
}

.actions-column {
  width: 1%;
  white-space: nowrap;
}

.stock-number {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.status,
.availability {
  display: inline-block;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  white-space: nowrap;
}

.status.active,
.availability.in_stock {
  color: var(--success-color);
}

.status.archived,
.availability.untracked {
  color: var(--text-muted);
}

.status.draft {
  color: var(--text-secondary);
}

.availability.out_of_stock {
  color: var(--error-color);
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

@media (max-width: 760px) {
  .store-page {
    padding: 1rem;
  }

  .page-header,
  .section-header,
  .pager {
    align-items: stretch;
    flex-direction: column;
  }

  .adjustment-grid {
    grid-template-columns: 1fr;
  }
}
</style>
