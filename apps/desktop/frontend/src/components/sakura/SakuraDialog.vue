<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import SakuraButton from "./SakuraButton.vue";

const props = defineProps<{
  open: boolean;
  title: string;
  danger?: boolean;
}>();

const emit = defineEmits<{ close: []; confirm: [] }>();
const dialogRef = ref<HTMLDivElement | null>(null);
const previousActiveElement = ref<HTMLElement | null>(null);
const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

function focusableElements(): HTMLElement[] {
  const dialog = dialogRef.value;
  if (!dialog) {
    return [];
  }
  return Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) => !element.hasAttribute("disabled") && element.getAttribute("aria-hidden") !== "true"
  );
}

function focusInitialElement() {
  const first = focusableElements()[0];
  (first ?? dialogRef.value)?.focus();
}

function restorePreviousFocus() {
  previousActiveElement.value?.focus();
  previousActiveElement.value = null;
}

function keepFocusInside(event: FocusEvent) {
  const dialog = dialogRef.value;
  if (!props.open || !dialog) {
    return;
  }
  if (event.target instanceof Node && dialog.contains(event.target)) {
    return;
  }
  focusInitialElement();
}

watch(
  () => props.open,
  async (open, wasOpen) => {
    if (open) {
      previousActiveElement.value = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      document.addEventListener("focusin", keepFocusInside);
      await nextTick();
      focusInitialElement();
    } else if (wasOpen) {
      document.removeEventListener("focusin", keepFocusInside);
      await nextTick();
      restorePreviousFocus();
    }
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  document.removeEventListener("focusin", keepFocusInside);
  if (props.open) {
    restorePreviousFocus();
  }
});

function trapTab(event: KeyboardEvent) {
  const elements = focusableElements();
  if (!elements.length) {
    event.preventDefault();
    dialogRef.value?.focus();
    return;
  }

  const first = elements[0];
  const last = elements[elements.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") {
    emit("close");
  } else if (event.key === "Tab") {
    trapTab(event);
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="sakura-dialog-backdrop" @keydown="onKeydown">
      <div
        ref="dialogRef"
        class="sakura-dialog"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        tabindex="-1"
      >
        <header>
          <h2>{{ title }}</h2>
        </header>
        <div class="sakura-dialog__body">
          <slot />
        </div>
        <footer>
          <SakuraButton @click="$emit('close')">取消</SakuraButton>
          <SakuraButton :danger="danger" @click="$emit('confirm')">确认</SakuraButton>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.sakura-dialog-backdrop {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: var(--sakura-space-6);
  background: rgba(74, 48, 64, 0.22);
}

.sakura-dialog {
  width: min(480px, 100%);
  border: 2px solid var(--sakura-border-strong);
  border-radius: var(--sakura-radius-lg);
  background: var(--sakura-surface-solid);
  box-shadow: var(--sakura-shadow-md);
  padding: var(--sakura-space-5);
}

h2 {
  margin: 0;
  font-size: 1.2rem;
}

.sakura-dialog__body {
  margin: var(--sakura-space-4) 0;
}

footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sakura-space-2);
}
</style>
