<script setup lang="ts">
import { computed, ref } from 'vue'
import SakuraButton from './sakura/SakuraButton.vue'

const input = ref('')
const messages = ref<string[]>(['欢迎使用 Yumetsuki'])
const streaming = ref(false)
const lastFailedDraft = ref('')

const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)

function send() {
  if (!canSend.value) return
  const draft = input.value
  input.value = ''
  streaming.value = true
  messages.value.push(`你：${draft}`)
  window.setTimeout(() => {
    if (!streaming.value) return
    messages.value.push('Yumetsuki：mock streaming done')
    streaming.value = false
  }, 80)
}

function stop() {
  streaming.value = false
}

function retry() {
  if (!lastFailedDraft.value) return
  input.value = lastFailedDraft.value
}
</script>

<template>
  <section class="chat-panel" aria-label="聊天">
    <div class="chat-panel__messages" data-testid="chat-messages" aria-live="polite">
      <p v-for="message in messages" :key="message">{{ message }}</p>
    </div>
    <label class="chat-panel__input">
      <span>输入</span>
      <textarea v-model="input" data-testid="chat-input" rows="3" />
    </label>
    <div class="chat-panel__actions">
      <SakuraButton label="发送" :disabled="!canSend" @click="send" />
      <SakuraButton label="停止" :disabled="!streaming" @click="stop" />
      <SakuraButton label="重试" :disabled="!lastFailedDraft" @click="retry" />
    </div>
  </section>
</template>

<style scoped>
.chat-panel {
  display: grid;
  gap: 12px;
}

.chat-panel__messages {
  min-height: 180px;
  max-height: 42vh;
  overflow: auto;
  padding: 12px;
  border: 1px solid var(--sakura-color-border);
  border-radius: var(--sakura-radius-md);
  background: var(--sakura-color-surface);
}

.chat-panel__input {
  display: grid;
  gap: 6px;
  color: var(--sakura-color-text);
}

.chat-panel__input textarea {
  resize: vertical;
  min-height: 80px;
  border: 1px solid var(--sakura-color-border);
  border-radius: var(--sakura-radius-md);
  padding: 8px;
  font: 14px/1.5 var(--sakura-font-family);
}

.chat-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
