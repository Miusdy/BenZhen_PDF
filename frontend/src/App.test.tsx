import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

Object.defineProperty(window, "setInterval", { value: vi.fn(() => 1) });

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
});
