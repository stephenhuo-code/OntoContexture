import "@testing-library/jest-dom/vitest";

// jsdom 不执行布局；真实定位由浏览器验证。
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
