<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from "vue";
import { useChatStore } from "@/stores/chatStore";
import SakuraButton from "./sakura/SakuraButton.vue";
import SakuraIconButton from "./sakura/SakuraIconButton.vue";

const chatStore = useChatStore();
const inputId = "chat-input";
const visibleMessages = computed(() => chatStore.messages);

onMounted(() => {
  void chatStore.init();
});

onBeforeUnmount(() => {
  chatStore.dispose();
});
</script>

<template>
  <section class="chat-panel" aria-labelledby="chat-heading">
    <header class="chat-panel__header">
      <div>
        <h1 id="chat-heading">Yumetsuki</h1>
        <p>聊天工作台</p>
      </div>
      <div id="chat-status" data-testid="chat-status" class="chat-panel__status" role="status" aria-label="运行状态">
        {{ chatStore.statusText }}
      </div>
    </header>

    <div class="chat-panel__body" aria-live="polite">
      <article
        v-for="message in visibleMessages"
        :key="message.id"
        class="chat-message"
        :class="`role-${message.role}`"
      >
        <strong>{{ message.role === "user" ? "我" : message.role === "assistant" ? "Yumetsuki" : "系统" }}</strong>
        <p>{{ message.content }}</p>
      </article>
      <article v-if="chatStore.streamingDraft" class="chat-message role-assistant">
        <strong>Yumetsuki</strong>
        <p>{{ chatStore.streamingDraft }}</p>
      </article>
      <p v-if="!visibleMessages.length && !chatStore.streamingDraft" class="chat-panel__empty">
        发送消息以开始对话。
      </p>
    </div>

    <form class="chat-panel__composer" @submit.prevent="chatStore.send()">
      <label class="sr-only" :for="inputId">聊天输入</label>
      <textarea
        :id="inputId"
        v-model="chatStore.inputDraft"
        aria-label="聊天输入"
        rows="3"
        placeholder="输入消息..."
        :disabled="chatStore.busy"
      />
      <div class="chat-panel__actions">
        <SakuraButton v-if="chatStore.canRetry" aria-label="重试消息" @click="chatStore.retry()">重试</SakuraButton>
        <SakuraIconButton
          v-if="chatStore.busy"
          label="停止当前回复"
          danger
          @click="chatStore.stop()"
        >
          ■
        </SakuraIconButton>
        <SakuraIconButton v-else label="发送消息" @click="chatStore.send()"> &gt; </SakuraIconButton>
      </div>
    </form>
  </section>
</template>

<style scoped>
.chat-panel {
  display: grid;
  grid-template-rows: auto minmax(240px, 1fr) auto;
  gap: var(--sakura-space-4);
  min-height: 100%;
}

.chat-panel__header {
  display: flex;
  justify-content: space-between;
  gap: var(--sakura-space-4);
  align-items: flex-start;
}

h1 {
  margin: 0;
  font-size: clamp(1.6rem, 4vw, 2.4rem);
  letter-spacing: 0;
}

p {
  margin: 0;
}

.chat-panel__header p {
  color: var(--sakura-text-muted);
}

.chat-panel__status {
  min-width: 120px;
  padding: var(--sakura-space-2) var(--sakura-space-3);
  border: 2px solid var(--sakura-border);
  border-radius: var(--sakura-radius-md);
  background: rgba(255, 255, 255, 0.58);
  text-align: center;
}

.chat-panel__body {
  min-height: 0;
  overflow: auto;
  display: grid;
  align-content: start;
  gap: var(--sakura-space-3);
  padding: var(--sakura-space-4);
  border: 3px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-lg);
  background: rgba(255, 255, 255, 0.42);
}

.chat-message {
  max-width: min(760px, 100%);
  padding: var(--sakura-space-3) var(--sakura-space-4);
  border: 2px solid rgba(212, 86, 122, 0.34);
  border-radius: var(--sakura-radius-md);
  background: rgba(255, 255, 255, 0.64);
  overflow-wrap: anywhere;
}

.role-user {
  justify-self: end;
}

.role-assistant,
.role-system {
  justify-self: start;
}

.chat-panel__empty {
  color: var(--sakura-text-muted);
}

.chat-panel__composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--sakura-space-3);
  align-items: end;
}

textarea {
  width: 100%;
  resize: vertical;
  min-height: 72px;
  max-height: 180px;
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-md);
  padding: var(--sakura-space-3);
  color: var(--sakura-text);
  background: rgba(255, 255, 255, 0.68);
}

.chat-panel__actions {
  display: flex;
  align-items: center;
  gap: var(--sakura-space-2);
}

@media (max-width: 640px) {
  .chat-panel__header,
  .chat-panel__composer {
    grid-template-columns: 1fr;
  }

  .chat-panel__header {
    display: grid;
  }
}
</style>
