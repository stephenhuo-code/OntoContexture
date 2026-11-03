import { type ApiError, type Me, createBffClient } from "@contexture/ts-api";
import { zh } from "./i18n/zh-CN";

export const bff = createBffClient(window.location.origin);

export function toApiError(error: unknown, status: number): ApiError {
  if (
    error &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return {
      code: error.code,
      message: error.message,
      trace_id:
        "trace_id" in error && typeof error.trace_id === "string"
          ? error.trace_id
          : "",
    };
  }
  return { code: `http.${status}`, message: zh.httpFailure, trace_id: "" };
}
export class ApiFailure extends Error {
  constructor(
    public status: number,
    public error: ApiError = toApiError(undefined, status),
  ) {
    super(error.message);
    this.name = "ApiFailure";
  }
}
function readJson(text: unknown): unknown {
  try {
    return typeof text === "string" ? JSON.parse(text) : text;
  } catch {
    return undefined;
  }
}
export async function loadMe(signal?: AbortSignal): Promise<Me> {
  try {
    const { data, error, response } = await bff.GET("/bff/v1/me", {
      signal,
      cache: "no-store",
      parseAs: "text",
    });
    const body = readJson(data ?? error);
    if (response.status !== 200)
      throw new ApiFailure(response.status, toApiError(body, response.status));
    if (!body || typeof body !== "object") throw new ApiFailure(500);
    const user = body as Record<string, unknown>;
    if (
      typeof user.user_id !== "string" ||
      !user.user_id.trim() ||
      typeof user.tenant_id !== "string" ||
      !user.tenant_id.trim() ||
      (user.display_name != null && typeof user.display_name !== "string") ||
      (user.roles !== undefined &&
        (!Array.isArray(user.roles) ||
          !user.roles.every((role) => typeof role === "string")))
    )
      throw new ApiFailure(500);
    return {
      tenant_id: user.tenant_id,
      user_id: user.user_id,
      display_name:
        typeof user.display_name === "string" ? user.display_name : undefined,
      roles: Array.isArray(user.roles) ? user.roles.map(String) : undefined,
    };
  } catch (error) {
    if (error instanceof ApiFailure) throw error;
    throw new ApiFailure(0);
  }
}
export function safeReturnTo(value?: string | null): string {
  if (!value) return "/home";
  try {
    const decoded = decodeURIComponent(value);
    if (
      [value, decoded].some(
        (target) =>
          !target.startsWith("/") ||
          target.startsWith("//") ||
          target.includes("\\") ||
          Array.from(target).some(
            (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
          ),
      )
    )
      return "/home";
    if (
      new URL(decoded, window.location.origin).pathname.replace(/\/+$/, "") ===
      "/auth/error"
    )
      return "/home";
    return value;
  } catch {
    return "/home";
  }
}
export function loginUrl(returnTo?: string | null) {
  return `/bff/v1/auth/login?return_to=${encodeURIComponent(safeReturnTo(returnTo))}`;
}
export function login(
  returnTo = window.location.pathname + window.location.search,
) {
  window.location.assign(loginUrl(returnTo));
}
export async function logout(): Promise<void> {
  try {
    const response = await fetch("/bff/v1/auth/logout", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
    });
    if (response.status !== 204)
      throw new ApiFailure(
        response.status,
        toApiError(readJson(await response.text()), response.status),
      );
  } catch (error) {
    if (error instanceof ApiFailure) throw error;
    throw new ApiFailure(0);
  }
}
