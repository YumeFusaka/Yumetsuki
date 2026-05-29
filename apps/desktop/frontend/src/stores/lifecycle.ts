import type { UnlistenFn } from "@/client/types/rpc";

export interface StoreLifecycleState {
  initialized: boolean;
  subscriptions: UnlistenFn[];
  initCount: number;
  disposeCount: number;
  restartCount: number;
}

export function createLifecycleState(): StoreLifecycleState {
  return {
    initialized: false,
    subscriptions: [],
    initCount: 0,
    disposeCount: 0,
    restartCount: 0
  };
}

export function initLifecycle(lifecycle: StoreLifecycleState): boolean {
  if (lifecycle.initialized) {
    return false;
  }
  lifecycle.initialized = true;
  lifecycle.initCount += 1;
  return true;
}

export function trackSubscription(lifecycle: StoreLifecycleState, unsubscribe: UnlistenFn): void {
  lifecycle.subscriptions.push(unsubscribe);
}

export function disposeLifecycle(lifecycle: StoreLifecycleState): void {
  for (const unsubscribe of lifecycle.subscriptions.splice(0)) {
    unsubscribe();
  }
  lifecycle.initialized = false;
  lifecycle.disposeCount += 1;
}

export function restartLifecycle(lifecycle: StoreLifecycleState): void {
  lifecycle.restartCount += 1;
}
