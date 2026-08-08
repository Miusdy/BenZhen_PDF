import type { Preflight, Settings } from "./types";

const isTauri = () => "__TAURI_INTERNALS__" in window;

export async function choosePdf(): Promise<string | null> {
  if (!isTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({ multiple: false, directory: false, filters: [{ name: "PDF", extensions: ["pdf"] }] });
  return typeof selected === "string" ? selected : null;
}

export async function chooseDirectory(): Promise<string | null> {
  if (!isTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({ multiple: false, directory: true });
  return typeof selected === "string" ? selected : null;
}

export async function openPath(path: string): Promise<void> {
  if (!isTauri()) return;
  const { openPath: openLocalPath } = await import("@tauri-apps/plugin-opener");
  await openLocalPath(path);
}

export async function sendCommand(payload: Record<string, unknown>): Promise<void> {
  if (!isTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("send_sidecar_command", { payload });
}

export async function requestPreflight(path: string, password: string): Promise<Preflight | null> {
  if (!isTauri()) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<Preflight>("preflight", { inputPath: path, password: password || null });
}

export async function startJob(inputPath: string, outputDirectory: string, settings: Settings, password: string): Promise<string | null> {
  if (!isTauri()) return null;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<string>("start_conversion", {
    inputPath,
    outputDirectory,
    password: password || null,
    config: {
      language: settings.language,
      ocr: settings.ocr,
      dpi: settings.dpi,
      review_threshold: settings.reviewThreshold,
      max_workers: settings.maxWorkers,
      keep_intermediate: settings.keepIntermediate,
      mark_review_in_docx: settings.markReview,
    },
  });
}

export async function onSidecarMessage(callback: (message: Record<string, unknown>) => void): Promise<() => void> {
  if (!isTauri()) return () => undefined;
  const { listen } = await import("@tauri-apps/api/event");
  return listen<Record<string, unknown>>("sidecar-message", (event) => callback(event.payload));
}

