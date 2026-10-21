// 织境 bff 的类型化客户端（同源访问，浏览器只携带会话 Cookie）
import createClient from "openapi-fetch";

import type { components, paths } from "./bff";

export type ObjectListView = components["schemas"]["ObjectListView"];
export type ObjectTypeRef = components["schemas"]["ObjectTypeRef"];
export type ObjectInstance = components["schemas"]["ObjectInstance"];
export type Me = components["schemas"]["Me"];

/** 统一错误格式（contracts/schemas/error.json） */
export interface ApiError {
  code: string;
  message: string;
  trace_id: string;
  details?: Record<string, unknown>;
}

export function createBffClient(baseUrl = "") {
  return createClient<paths>({
    baseUrl,
    credentials: "same-origin",
    // 每次请求时取全局 fetch（便于测试替换，也兼容运行时注入的 fetch）
    fetch: (request) => globalThis.fetch(request),
  });
}

export type BffClient = ReturnType<typeof createBffClient>;
