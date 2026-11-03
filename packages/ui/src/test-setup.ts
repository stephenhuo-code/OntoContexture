import "@testing-library/jest-dom/vitest";

// jsdom 没有布局观测；实际定位和焦点样式由浏览器用例验证。
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);
