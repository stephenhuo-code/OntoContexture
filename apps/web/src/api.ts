import { type ApiError, createBffClient } from "@contexture/ts-api";

// 同源访问 bff（经 Envoy Gateway 的 /bff/*），浏览器只携带会话 Cookie
export const bff = createBffClient(window.location.origin);

/** 把 bff 的统一错误格式转为可显示的错误；非 JSON 响应（如网关错误页）也给出可读信息 */
export function toApiError(error: unknown, status: number): ApiError {
  if (error && typeof error === "object" && "code" in error)
    return error as ApiError;
  return { code: `http.${status}`, message: "请求失败", trace_id: "" };
}

export function login(returnTo = window.location.pathname) {
  window.location.href = `/bff/v1/auth/login?return_to=${encodeURIComponent(returnTo)}`;
}

export async function logout() {
  await fetch("/bff/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin",
  });
  window.location.href = "/";
}
