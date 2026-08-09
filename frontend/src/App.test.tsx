import "@testing-library/jest-dom/vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const bridge = vi.hoisted(() => ({
  chooseDirectory: vi.fn(),
  choosePdf: vi.fn(),
  listener: undefined as ((message: Record<string, unknown>) => void) | undefined,
  onSidecarMessage: vi.fn(),
  openPath: vi.fn(),
  requestPreflight: vi.fn(),
  sendCommand: vi.fn(),
  startJob: vi.fn(),
}));

vi.mock("./bridge", () => ({
  chooseDirectory: bridge.chooseDirectory,
  choosePdf: bridge.choosePdf,
  onSidecarMessage: bridge.onSidecarMessage,
  openPath: bridge.openPath,
  requestPreflight: bridge.requestPreflight,
  sendCommand: bridge.sendCommand,
  startJob: bridge.startJob,
}));

Object.defineProperty(window, "setInterval", { value: vi.fn(() => 1) });

const preflight = {
  input_path: "/tmp/input.pdf",
  input_name: "input.pdf",
  file_size: 1024,
  total_pages: 2,
  encrypted: false,
  has_text_layer: true,
  estimated_scan_pages: 0,
  estimated_ocr_pages: 0,
  estimated_seconds: 1,
  estimated_temp_bytes: 2048,
};

beforeEach(() => {
  vi.clearAllMocks();
  bridge.listener = undefined;
  bridge.choosePdf.mockResolvedValue(null);
  bridge.chooseDirectory.mockResolvedValue(null);
  bridge.requestPreflight.mockResolvedValue(null);
  bridge.startJob.mockResolvedValue(null);
  bridge.sendCommand.mockResolvedValue(undefined);
  bridge.onSidecarMessage.mockImplementation(async (callback) => {
    bridge.listener = callback;
    return () => undefined;
  });
});

describe("App", () => {
  it("shows privacy promise and required workflow controls", () => {
    render(<App />);
    expect(screen.getByText("文件仅在当前设备上处理，不会上传到服务器。")).toBeInTheDocument();
    expect(screen.getAllByText("选择 PDF").length).toBeGreaterThan(0);
    expect(screen.getByText("高级设置")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始转换/ })).toBeDisabled();
  });

  it("accepts a browser PDF and completes preflight fallback", async () => {
    render(<App />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["pdf"], "中文 测试.pdf", { type: "application/pdf" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText("正在读取 PDF…")).toBeInTheDocument();
    expect(screen.getByText("大型文件可能需要一些时间，请勿关闭窗口")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("预检完成 · 未发现文件访问问题")).toBeInTheDocument());
    expect(screen.getByText("中文 测试.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /开始转换/ })).toBeEnabled();
  });

  it("allows cancelling a long preflight and ignores its late result", async () => {
    render(<App />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["pdf"], "大型文件.pdf", { type: "application/pdf" })] } });
    fireEvent.click(screen.getByRole("button", { name: "取消读取" }));
    expect(screen.queryByText("正在读取 PDF…")).not.toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 1100));
    expect(screen.queryByText("大型文件.pdf")).not.toBeInTheDocument();
    expect(screen.getAllByText("选择 PDF").length).toBeGreaterThan(0);
  });

  it("reports a native start failure instead of leaving an unhandled rejection", async () => {
    bridge.choosePdf.mockResolvedValue("/tmp/input.pdf");
    bridge.requestPreflight.mockResolvedValue(preflight);
    bridge.startJob.mockRejectedValue(new Error("sidecar failed"));
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /选择 PDF/ }));
    await waitFor(() => expect(screen.getByText("预检完成 · 未发现文件访问问题")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /开始转换/ }));

    await waitFor(() => {
      expect(screen.getByText("sidecar failed")).toBeInTheDocument();
      expect(document.querySelector("footer")).toHaveTextContent("发生错误");
    });
  });

  it("disables duplicate starts while paused", async () => {
    bridge.choosePdf.mockResolvedValue("/tmp/input.pdf");
    bridge.requestPreflight.mockResolvedValue(preflight);
    bridge.startJob.mockResolvedValue("job-1");
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /选择 PDF/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /开始转换/ })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: /开始转换/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "暂停" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "暂停" }));

    await waitFor(() => expect(bridge.sendCommand).toHaveBeenCalledWith({ command: "pause", job_id: "job-1" }));
    expect(screen.getByRole("button", { name: /开始转换/ })).toBeDisabled();
    act(() => {
      bridge.listener?.({ type: "cancelled", job_id: "job-1", message: "任务已取消" });
    });
    expect(screen.getByText("任务已取消")).toBeInTheDocument();
    expect(document.querySelector(".error-message")).not.toBeInTheDocument();
  });

  it("ignores late events from a job after its file is removed", async () => {
    bridge.choosePdf.mockResolvedValue("/tmp/input.pdf");
    bridge.requestPreflight.mockResolvedValue(preflight);
    bridge.startJob.mockResolvedValue("job-1");
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /选择 PDF/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: /开始转换/ })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: /开始转换/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "暂停" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "移除文件" }));
    act(() => {
      bridge.listener?.({
        type: "complete",
        job_id: "job-1",
        payload: { output_docx: "/tmp/input.docx" },
      });
    });

    expect(screen.queryByText("转换完成！")).not.toBeInTheDocument();
    expect(screen.getAllByText("选择 PDF").length).toBeGreaterThan(0);
  });
});
