import type { ApiError, ObjectListView } from "@contexture/ts-api";
import { useEffect, useState } from "react";
import { useParams } from "react-router";

import { bff, toApiError } from "../api";
import { ErrorBanner } from "../components/ErrorBanner";

const LEVELS: Record<number, string> = { 1: "一级", 2: "二级", 3: "三级" };

export function ObjectsPage() {
  const { typeKey = "equipment" } = useParams();
  const [view, setView] = useState<ObjectListView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let active = true;
    setView(null);
    setError(null);
    bff
      .GET("/bff/v1/object-types/{typeKey}/objects", {
        params: { path: { typeKey }, query: { limit: 20 } },
      })
      .then(({ data, error: err, response }) => {
        if (!active) return;
        if (data) setView(data);
        else setError(toApiError(err, response.status));
      })
      .catch(() => active && setError(toApiError(null, 0)));
    return () => {
      active = false;
    };
  }, [typeKey]);

  if (error) return <ErrorBanner error={error} />;
  if (!view) return <p className="muted">加载中…</p>;

  const { object_type: type, items } = view;
  const columns = type.attributes.map((a) => a.name);
  return (
    <section>
      <h1>
        {type.display_name ?? type.name}
        <span className="muted"> {type.name}</span>
      </h1>

      <h2>对象定义（OpenMetadata，已审批）</h2>
      <table aria-label="对象定义">
        <caption>
          <code>{type.type_uri}</code> · 版本 {type.version}
        </caption>
        <thead>
          <tr>
            <th>属性</th>
            <th>数据类型</th>
            <th>必填</th>
            <th>数据级别</th>
          </tr>
        </thead>
        <tbody>
          {type.attributes.map((a) => (
            <tr key={a.name}>
              <td>{a.name}</td>
              <td>{a.data_type}</td>
              <td>{a.required ? "是" : "否"}</td>
              <td>{a.data_level ? LEVELS[a.data_level] : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>对象列表（Doris 本体实例库，经 AI 网关取数）</h2>
      <table aria-label="对象列表">
        <thead>
          <tr>
            <th>对象 URI</th>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.object_uri}>
              <td>
                <code>{item.object_uri}</code>
              </td>
              {columns.map((c) => (
                <td key={c}>{String(item.attributes[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        共 {items.length} 行 · 本次请求 trace <code>{view.trace_id}</code>（可在
        Langfuse 中查询全链路）
      </p>
    </section>
  );
}
