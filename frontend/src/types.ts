export type JobPhase = "idle" | "preflight" | "ready" | "running" | "paused" | "completed" | "failed" | "cancelled";

export interface Preflight {
  input_path: string;
  input_name: string;
  file_size: number;
  total_pages: number;
  encrypted: boolean;
  has_text_layer: boolean;
  estimated_scan_pages: number;
  estimated_ocr_pages: number;
  estimated_seconds: number;
  estimated_temp_bytes: number;
}

export interface Settings {
  ocr: "auto" | "always" | "never";
  language: string;
  dpi: number;
  reviewThreshold: number;
  maxWorkers: number;
  keepIntermediate: boolean;
  markReview: boolean;
  htmlReport: boolean;
  jsonReport: boolean;
}

export interface ProgressState {
  stage: string;
  currentPage: number;
  totalPages: number;
  progress: number;
  message: string;
  reviewIssues: number;
  criticalConflicts: number;
}
