# Local Memory and Settings Reuse Design

Date: 2026-05-20

## Goal

Address two concrete issues in the current desktop pet application:

1. Prevent the chat window's "Open Settings" action from spawning unlimited settings windows.
2. Replace the current cloud-oriented memory bootstrap with a configurable local memory setup based on Mem0 OSS with local Chroma persistence, while keeping the main chat LLM on the existing remote provider.

## Scope

This design covers:

- Settings window reuse and activation behavior.
- Local memory configuration schema, persistence, and settings UI.
- Startup wiring that creates a local Mem0-backed memory store when enabled.
- Tests for the changed behavior.

This design does not cover:

- Moving the main LLM to local execution.
- Exposing advanced vector DB or embedding controls in the first iteration.
- Migrating or importing historical remote memory data.

## Current Problems

### Settings window behavior

`ChatWindow._open_settings()` currently creates a new `SettingsWindow` every time the context menu action is used. This leads to unbounded duplicate windows and loses the user's mental model of "the settings window".

### Memory architecture mismatch

The current memory bootstrap looks for `MEM0_API_KEY` and instantiates `MemoryClient`, which is aligned with a cloud-style setup. That conflicts with the new requirement: memory data must stay local and lightweight, while the main LLM may remain remote.

## Recommended Approach

Implement a dedicated local memory configuration and keep it separate from API configuration.

Why this approach:

- It keeps local persistence concerns out of the API settings page.
- It gives a stable place for future memory settings without reopening the config model design.
- It avoids hardcoding local storage paths into startup logic.

## Design

### 1. Settings window lifecycle

Make settings windows single-instance from the point of view of the chat window:

- `ChatWindow` receives an optional callable or window reference that can supply the shared settings window.
- When the user selects "Open Settings":
  - If a settings window already exists and is still alive, call `show()`, `raise()`, and `activateWindow()`.
  - If no settings window exists, create one, store the reference, then show it.
- When the shared settings window is closed, clear the stored reference so a future action can recreate it.

Behavioral result:

- Repeated right-click -> "Open Settings" reuses the same window.
- Closed settings window can still be reopened normally.

### 2. Memory configuration model

Add a dedicated memory configuration model and file.

Config model fields:

- `enabled: bool` — whether local memory is active.
- `storage_dir: str` — base directory for local memory persistence.
- `user_id: str` — logical memory namespace for the user.
- `top_k: int` — max retrieved memories per query.

Persistence:

- Add `MemoryConfig` to `config/schema.py`.
- Add load/save support in `ConfigManager`.
- Store config in `data/config/memory.yaml`.

Defaults:

- `enabled = false`
- `storage_dir = "data/memory"`
- `user_id = "default-user"`
- `top_k = 5`

These defaults are simple, local, and predictable.

### 3. Settings UI

Add a dedicated "记忆" page to the settings window.

Controls:

- Enable local memory: checkbox
- Storage directory: line edit
- User ID: line edit
- Retrieval count (`top_k`): numeric input

UI behavior:

- The page uses the same visual language as the existing settings pages.
- Saving persists `memory.yaml` through `ConfigManager`.
- No cloud API key fields are shown on this page.

### 4. Local Mem0 bootstrap

Replace the cloud-style memory bootstrap with a local builder.

Startup behavior:

- `SettingsWindow._launch_chat()` reads `self._config.memory`.
- If memory is disabled, pass `None` as the memory store.
- If memory is enabled:
  - Create a local Mem0 OSS instance.
  - Configure it to persist to a local Chroma path under `storage_dir`.
  - Wrap it with `Mem0MemoryStore`.

Operational model:

- Conversation memory retrieval and writes stay local on disk.
- Main chat generation continues using the existing remote LLM config.
- The local memory path becomes part of normal app data and can be backed up or deleted by the user.

### 5. `Mem0MemoryStore` responsibilities

Keep `Mem0MemoryStore` thin:

- `search_relevant(query, user_id)` returns plain memory strings.
- `add_conversation(user_text, assistant_text, user_id)` appends the two-message turn.
- Respect `top_k` from config during retrieval.

It should not own UI logic or app config parsing.

### 6. Testing strategy

Use test-first changes for the new behavior.

Required tests:

- Settings reuse:
  - opening settings twice reuses the same window reference
  - reopening after close creates a fresh window
- Config manager:
  - reads default memory config
  - saves and reloads `memory.yaml`
- Local memory creation:
  - disabled memory returns `None`
  - enabled memory builds a local Mem0-backed store using configured path
- Existing agent flow:
  - memory retrieval still injects context
  - memory writes still occur after assistant reply

## Error Handling

- If local memory is enabled but Mem0 or its local dependencies are unavailable, startup should fail with a clear user-facing error instead of silently disabling memory.
- If the configured storage directory is invalid, startup should surface the path error clearly.
- If `user_id` is blank, normalize it to the configured default before memory startup.

## Tradeoffs

Accepted tradeoffs:

- This first iteration exposes only a small memory surface area. Advanced embedding or vector-store tuning stays out of scope.
- The local memory stack may still use remote services indirectly if the future Mem0 extraction or embedding configuration is expanded incorrectly. For this iteration, only persistence locality is guaranteed by design; the main LLM remains remote by intent.

## Implementation Boundaries

Expected files to change:

- `config/schema.py`
- `config/manager.py`
- `ui/settings/window.py`
- `ui/settings/pages/` (new memory page)
- `ui/chat/window.py`
- `memory/mem0_store.py`
- tests for config, UI behavior, and memory bootstrap

Expected new file:

- `data/config/memory.yaml` template is optional; runtime creation via save is acceptable

## Success Criteria

- Right-clicking "Open Settings" from the chat window never creates duplicate live settings windows.
- Closing the settings window and reopening it works.
- Users can enable local memory and choose where it persists.
- Memory persistence is local to the machine via configured local storage.
- Chat continues to use the existing remote LLM setup.
