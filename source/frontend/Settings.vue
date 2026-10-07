<template>
  <main class="store-page">
    <section class="panel">
      <h1>{{ t('Настройки на магазина', 'Store settings') }}</h1>
      <p>
        {{
          t(
            'Настройките на магазина идват в следващата стъпка на S1.',
            'Store-owned settings arrive in the next S1 increment.',
          )
        }}
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useStoreLanguage } from './language'

const { t } = useStoreLanguage()
</script>

<style scoped>
.store-page {
  max-width: 72rem;
  margin: 0 auto;
  padding: 2rem;
  color: var(--text-primary);
}

.panel {
  padding: 1rem;
  border: 1px solid var(--card-border);
  border-radius: var(--border-radius-md);
  background: var(--card-bg);
  color: var(--text-primary);
}

p {
  color: var(--text-secondary);
}
</style>
