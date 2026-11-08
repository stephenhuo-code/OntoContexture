import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiError } from "@contexture/ts-api";
import { ApiFailure } from "../../api";

export type Load<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: T };

export function asApiError(e: unknown): ApiError {
  return e instanceof ApiFailure
    ? e.error
    : { code: "http.0", message: "请求失败，请稍后重试", trace_id: "" };
}

/** 读取 BFF 数据；出错如实保留错误，不回退任何示例数据（宪法 v2.2.0）。 */
export function useLoad<T>(fetcher: () => Promise<T>, deps: unknown[]) {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const seq = useRef(0);
  const reload = useCallback((quiet = false) => {
    const id = ++seq.current;
    if (!quiet) setState({ status: "loading" });
    fetcher().then(
      (data) => id === seq.current && setState({ status: "ready", data }),
      (e: unknown) =>
        id === seq.current &&
        setState({ status: "error", error: asApiError(e) }),
    );
  }, deps);
  useEffect(() => reload(), [reload]);
  /** 以写操作返回的最新数据替换（BFF 返回即 OM 的最新状态） */
  const set = useCallback((data: T) => {
    seq.current++;
    setState({ status: "ready", data });
  }, []);
  return { state, reload, set };
}
