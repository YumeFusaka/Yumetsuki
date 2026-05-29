<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <section class="sakura-settings-section" :aria-labelledby="`${title}-heading`">
    <header>
      <h2 :id="`${title}-heading`">{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </header>
    <div class="sakura-settings-section__content">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.sakura-settings-section {
  padding: var(--sakura-space-5) 0;
  border-top: 1px solid rgba(212, 86, 122, 0.28);
}

h2 {
  margin: 0;
  font-size: 1.1rem;
}

p {
  margin: var(--sakura-space-1) 0 0;
  color: var(--sakura-text-muted);
}

.sakura-settings-section__content {
  margin-top: var(--sakura-space-4);
  display: grid;
  gap: var(--sakura-space-3);
}
</style>
