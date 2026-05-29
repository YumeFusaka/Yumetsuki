import type { ConfigSnapshot } from "./rpc";

export type { ConfigSnapshot };

export type SystemConfigDraft = ConfigSnapshot["system"] & {
  passive_ocr_enabled?: boolean;
};
