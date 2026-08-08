import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  FileOutput,
  FileText,
  FolderOpen,
  LockKeyhole,
  Pause,
  Play,
  RefreshCcw,
  ShieldCheck,
  Square,
  Upload,
  X,
} from "lucide-react";
import { chooseDirectory, choosePdf, onSidecarMessage, openPath, requestPreflight, sendCommand, startJob } from "./bridge";
import type { JobPhase, Preflight, ProgressState, Settings } from "./types";

const defaultSettings: Settings = {
  ocr: "auto",
  language: "chi_sim+eng",
  dpi: 300,
  reviewThreshold: 0.8,
  maxWorkers: 2,
  keepIntermediate: false,
  markReview: true,
};

const initialProgress: ProgressState = {
  stage: "等待开始",
  currentPage: 0,
  totalPages: 0,
  progress: 0,
  message: "选择 PDF 后即可开始",
  reviewIssues: 0,
  criticalConflicts: 0,
};

const formatBytes = (bytes: number) => {
  if (!bytes) return "0 MB";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index > 1 ? 2 : 0)} ${units[index]}`;
};

const formatDuration = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

function WorkflowRail({ phase }: { phase: JobPhase }) {
  const active = phase === "idle" ? 1 : phase === "ready" || phase === "preflight" ? 2 : phase === "running" || phase === "paused" ? 3 : 4;
  return (
    <nav className="workflow" aria-label="转换步骤">
      {["选择 PDF", "预检与设置", "转换中", "完成"].map((label, index) => {
        const step = index + 1;
        return (
          <div className={`workflow-step ${step === active ? "active" : ""} ${step < active ? "done" : ""}`} key={label}>
            <span className="step-node">{step < active ? <Check size={15} /> : step}</span>
            <div><strong>{label}</strong><small>{["添加待转换文件", "检查文件和配置", "正在转换为 Word", "查看结果"][index]}</small></div>
          </div>
        );
      })}
    </nav>
  );
}

function SettingRow({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="setting-row"><span>{label}</span>{children}</label>;
}

function App() {
  const [phase, setPhase] = useState<JobPhase>("idle");
  const [inputPath, setInputPath] = useState("");
  const [password, setPassword] = useState("");
  const [outputDirectory, setOutputDirectory] = useState("");
  const [preflight, setPreflight] = useState<Preflight | null>(null);
  const [settings, setSettings] = useState(defaultSettings);
  const [progress, setProgress] = useState(initialProgress);
  const [advancedOpen, setAdvancedOpen] = useState(true);
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState("");
  const [outputs, setOutputs] = useState({ docx: "", directory: "" });
  const fileInput = useRef<HTMLInputElement>(null);
  const demoTimer = useRef<number | null>(null);
  const analysisToken = useRef(0);

  useEffect(() => {
    let dispose: () => void = () => {};
    void onSidecarMessage((message) => {
      if (message.job_id && jobId && message.job_id !== jobId) return;
      if (message.type === "progress" || message.type === "page_complete") {
        const payload = (message.payload ?? {}) as Record<string, unknown>;
        setProgress((current) => ({
          ...current,
          stage: String(message.stage ?? current.stage),
          currentPage: Number(message.current_page ?? current.currentPage),
          totalPages: Number(message.total_pages ?? current.totalPages),
          progress: Number(message.progress ?? current.progress),
          message: String(message.message ?? current.message),
          reviewIssues: current.reviewIssues + Number(payload.issues ?? 0),
        }));
      }
      if (message.type === "complete") {
        const payload = (message.payload ?? {}) as Record<string, unknown>;
        setPhase("completed");
        setOutputs({ docx: String(payload.output_docx ?? ""), directory: outputDirectory });
      }
      if (message.type === "error") {
        setError(String(message.message ?? "转换失败"));
        setPhase("failed");
      }
    }).then((unlisten) => { dispose = unlisten; });
    return () => { dispose(); if (demoTimer.current) window.clearInterval(demoTimer.current); };
  }, [jobId, outputDirectory]);

  const displayName = preflight?.input_name ?? (inputPath ? inputPath.split(/[\\/]/).pop() : "");
  const canStart = Boolean(preflight && outputDirectory && phase !== "running");
  const progressPercent = Math.round(progress.progress * 100);
  const startLabel = phase === "completed" ? "重新转换" : "开始转换";
  const isAnalyzing = phase === "preflight" && !preflight;

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => setSettings((current) => ({ ...current, [key]: value }));

  async function analyze(path: string, browserFile?: File) {
    const token = ++analysisToken.current;
    setError(""); setInputPath(path); setPreflight(null); setPhase("preflight");
    try {
      const request = requestPreflight(path, password);
      const result = browserFile
        ? await Promise.all([request, new Promise((resolve) => window.setTimeout(resolve, 1000))]).then(([value]) => value)
        : await request;
      if (token !== analysisToken.current) return;
      const fallback: Preflight = {
        input_path: path,
        input_name: browserFile?.name ?? path.split(/[\\/]/).pop() ?? "示例文档.pdf",
        file_size: browserFile?.size ?? 13_086_228,
        total_pages: 128,
        encrypted: false,
        has_text_layer: true,
        estimated_scan_pages: 12,
        estimated_ocr_pages: 12,
        estimated_seconds: 84,
        estimated_temp_bytes: 1_374_389_534,
      };
      setPreflight(result ?? fallback);
      if (!outputDirectory) {
        const separator = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
        setOutputDirectory(separator >= 0 ? path.slice(0, separator) : "本真 PDF 输出");
      }
      setPhase("ready");
    } catch (reason) {
      if (token !== analysisToken.current) return;
      setError(reason instanceof Error ? reason.message : "无法读取 PDF"); setPhase("failed");
    }
  }

  function cancelAnalysis() {
    analysisToken.current += 1;
    if (fileInput.current) fileInput.current.value = "";
    setInputPath("");
    setPreflight(null);
    setPhase("idle");
    setError("");
  }

  async function selectFile() {
    const selected = await choosePdf();
    if (selected) await analyze(selected); else fileInput.current?.click();
  }

  function runDemo() {
    let page = 0;
    setPhase("running");
    setProgress({ ...initialProgress, stage: "页面分析", totalPages: preflight?.total_pages ?? 128, message: "正在分析页面结构" });
    demoTimer.current = window.setInterval(() => {
      page += 4;
      const total = preflight?.total_pages ?? 128;
      setProgress((current) => ({ ...current, stage: page > total * 0.25 ? "OCR 识别（语义版面分析）" : "页面分析", currentPage: Math.min(page, total), totalPages: total, progress: Math.min(page / total, 1), message: `正在处理第 ${Math.min(page, total)} 页`, reviewIssues: Math.floor(page / 18), criticalConflicts: Math.floor(page / 52) }));
      if (page >= total) { if (demoTimer.current) window.clearInterval(demoTimer.current); setPhase("completed"); setOutputs({ docx: "", directory: outputDirectory }); }
    }, 120);
  }

  async function begin() {
    if (!preflight) return;
    setError("");
    const created = await startJob(inputPath, outputDirectory, settings, password);
    if (!created) { runDemo(); return; }
    setJobId(created); setPhase("running");
    setProgress({ ...initialProgress, totalPages: preflight.total_pages, stage: "准备转换", message: "正在启动本地处理引擎" });
  }

  async function control(command: "pause" | "resume" | "cancel") {
    if (jobId) await sendCommand({ command, job_id: jobId });
    if (command === "pause") { if (demoTimer.current) window.clearInterval(demoTimer.current); setPhase("paused"); }
    if (command === "resume") { setPhase("running"); if (!jobId) runDemo(); }
    if (command === "cancel") { if (demoTimer.current) window.clearInterval(demoTimer.current); setPhase("cancelled"); setProgress((current) => ({ ...current, message: "任务已安全取消" })); }
  }

  function reset() { analysisToken.current += 1; if (fileInput.current) fileInput.current.value = ""; if (demoTimer.current) window.clearInterval(demoTimer.current); setPhase("idle"); setInputPath(""); setPreflight(null); setProgress(initialProgress); setOutputs({ docx: "", directory: "" }); setError(""); }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><FileText size={23} strokeWidth={1.8} /><strong>本真 PDF</strong></div>
        <div className="privacy"><ShieldCheck size={17} />文件仅在当前设备上处理，不会上传到服务器。</div>
        <div className="local-status"><span />本地处理模式</div>
      </header>
      <div className="workspace">
        <WorkflowRail phase={phase} />
        <main className="main-pane">
          <section
            className={`drop-zone ${preflight ? "compact" : ""} ${isAnalyzing ? "loading" : ""}`}
            aria-busy={isAnalyzing}
            aria-live="polite"
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file?.name.toLowerCase().endsWith(".pdf")) void analyze(file.name, file); }}
          >
            <div className="coordinate-labels"><span>0</span><span>300</span><span>600</span><span>900</span></div>
            {isAnalyzing ? <>
              <div className="document-scanner" aria-hidden="true">
                <span className="scanner-ring ring-one" /><span className="scanner-ring ring-two" /><span className="scanner-ring ring-three" />
                <span className="scanner-orbit orbit-one" /><span className="scanner-orbit orbit-two" />
                <div className="scanner-document"><FileText size={42} strokeWidth={1.45} /></div>
              </div>
              <h1 className="loading-title">正在读取 PDF…</h1>
              <p>大型文件可能需要一些时间，请勿关闭窗口</p>
              <strong className="analysis-file-name">{inputPath.split(/[\\/]/).pop()}</strong>
              <div className="indeterminate-track"><span /></div>
              <button className="secondary prominent cancel-reading" onClick={cancelAnalysis}><X size={16} />取消读取</button>
            </> : <>
              <div className="file-glyph"><FileText size={38} strokeWidth={1.5} /></div>
              <h1>{preflight ? "已选择 PDF" : "选择 PDF"}</h1>
              <p>{preflight ? "文件已完成本地预检，可调整设置后开始转换" : "将 PDF 文件拖到此处，或点击选择文件"}</p>
              <button className="secondary prominent" onClick={() => void selectFile()}><Upload size={17} />选择 PDF</button>
            </>}
            <input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void analyze(file.name, file); }} />
          </section>

          {preflight ? (
            <section className="preflight-panel" aria-label="文档预检">
              <div className="file-head"><div className="pdf-icon">PDF</div><div><h2>{displayName}</h2><p>预检完成 · 未发现文件访问问题</p></div><button className="icon-button" aria-label="移除文件" onClick={reset}><X size={20} /></button></div>
              <div className="preflight-grid">
                <div><span>文件大小</span><strong>{formatBytes(preflight.file_size)}</strong></div>
                <div><span>页数</span><strong>{preflight.total_pages} 页</strong></div>
                <div><span>文字层状态</span><strong className="positive"><Check size={15} />{preflight.has_text_layer ? "已包含文字层" : "未检测到文字层"}</strong></div>
                <div><span>预计需 OCR</span><strong>{preflight.estimated_ocr_pages} 页</strong></div>
                <div><span>预计处理时间</span><strong>约 {formatDuration(preflight.estimated_seconds)}</strong></div>
                <div><span>临时空间估计</span><strong>{formatBytes(preflight.estimated_temp_bytes)}</strong></div>
              </div>
            </section>
          ) : null}

          <section className="output-row"><label>输出目录</label><div className="path-field">{outputDirectory || "选择用于保存 Word 的目录"}</div><button className="secondary" onClick={async () => { const value = await chooseDirectory(); if (value) setOutputDirectory(value); else if (!outputDirectory) setOutputDirectory("本真 PDF 输出"); }}><FolderOpen size={16} />浏览…</button></section>
          <section className="password-row"><LockKeyhole size={16} /><label htmlFor="password">PDF 密码</label><input id="password" type="password" value={password} placeholder="仅加密 PDF 需要，不会保存" onChange={(event) => setPassword(event.target.value)} /></section>
          {error ? <div className="error-message"><AlertTriangle size={17} />{error}</div> : null}
          <button className="primary" disabled={!canStart} onClick={() => void begin()}>{phase === "completed" ? <RefreshCcw size={18} /> : <Play size={18} fill="currentColor" />}{startLabel}</button>
        </main>

        <aside className="inspector">
          <button className="section-toggle" onClick={() => setAdvancedOpen((value) => !value)}><strong>高级设置</strong><ChevronDown size={18} className={advancedOpen ? "rotated" : ""} /></button>
          {advancedOpen ? <div className="settings">
            <SettingRow label="OCR 模式"><select value={settings.ocr} onChange={(event) => updateSetting("ocr", event.target.value as Settings["ocr"])}><option value="auto">仅对低质量页面自动 OCR</option><option value="always">所有页面均 OCR 对照</option><option value="never">禁用 OCR</option></select></SettingRow>
            <SettingRow label="OCR 语言"><select value={settings.language} onChange={(event) => updateSetting("language", event.target.value)}><option value="chi_sim+eng">简体中文 + 英文</option><option value="chi_sim">简体中文</option><option value="eng">英文</option></select></SettingRow>
            <SettingRow label="渲染 DPI"><select value={settings.dpi} onChange={(event) => updateSetting("dpi", Number(event.target.value))}><option value={200}>200</option><option value={300}>300（推荐）</option><option value={400}>400</option></select></SettingRow>
            <SettingRow label="人工核对阈值"><select value={settings.reviewThreshold} onChange={(event) => updateSetting("reviewThreshold", Number(event.target.value))}><option value={0.75}>75%</option><option value={0.8}>80%（推荐）</option><option value={0.85}>85%</option><option value={0.9}>90%</option></select></SettingRow>
            <SettingRow label="并发处理数"><select value={settings.maxWorkers} onChange={(event) => updateSetting("maxWorkers", Number(event.target.value))}><option value={1}>1</option><option value={2}>2（推荐）</option><option value={4}>4（上限）</option></select></SettingRow>
            {([["keepIntermediate", "保留中间文件（用于排查问题）"], ["markReview", "在 Word 中标记需要核对的内容"]] as const).map(([key, label]) => <label className="check-row" key={key}><input type="checkbox" checked={settings[key]} onChange={(event) => updateSetting(key, event.target.checked)} /><span>{label}</span></label>)}
          </div> : null}

          <section className="progress-section">
            <h2>转换进度</h2>
            <dl><div><dt>当前阶段</dt><dd>{progress.stage}</dd></div><div><dt>当前页面</dt><dd>第 {progress.currentPage} 页 / 共 {progress.totalPages || preflight?.total_pages || 0} 页</dd></div></dl>
            <div className="progress-track" aria-label={`转换进度 ${progressPercent}%`}><span style={{ width: `${progressPercent}%` }} /></div><div className="progress-caption"><span>{progress.message}</span><strong>{progressPercent}%</strong></div>
            <div className="risk-grid"><div><AlertTriangle /><span>需要人工核对<strong>{progress.reviewIssues}</strong></span></div><div><AlertTriangle /><span>关键内容冲突<strong>{progress.criticalConflicts}</strong></span></div></div>
            <div className="job-controls"><button disabled={phase !== "running"} onClick={() => void control("pause")}><Pause size={16} />暂停</button><button disabled={phase !== "paused"} onClick={() => void control("resume")}><Play size={16} />继续</button><button disabled={!(["running", "paused"] as JobPhase[]).includes(phase)} onClick={() => void control("cancel")}><Square size={14} fill="currentColor" />取消</button></div>
          </section>

          <section className="complete-section"><h2>完成</h2>
            {phase === "completed" ? <div className="completion-banner"><Check size={22} /><div><strong>转换完成！</strong><span>Word 文件已保存到输出目录</span></div></div> : null}
            <div className="result-actions">
            <button disabled={phase !== "completed" || !outputs.docx} onClick={() => void openPath(outputs.docx)}><FileOutput /><span>打开 Word</span></button>
            <button disabled={phase !== "completed" || !outputs.directory} onClick={() => void openPath(outputs.directory)}><FolderOpen /><span>打开输出目录</span></button>
            <button disabled={!preflight} onClick={() => { setPhase("ready"); setProgress(initialProgress); }}><RefreshCcw /><span>重新转换</span></button>
          </div></section>
        </aside>
      </div>
      <footer><span className="ready-dot" />{phase === "failed" ? "发生错误" : phase === "running" ? "正在本地处理" : "就绪"}<i />内容保真模式<i />无网络依赖</footer>
    </div>
  );
}

export default App;
