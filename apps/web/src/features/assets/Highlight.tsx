import type { TextSegment } from "@contexture/ts-api";

/** 命中词高亮：BFF 已把 OM 高亮解析为纯文本片段，这里只按片段渲染文本，不插入 HTML（research R8） */
export function Highlight({
  segments,
  fallback,
}: {
  segments?: TextSegment[];
  fallback?: string | null;
}) {
  if (!segments?.length) return <>{fallback ?? ""}</>;
  return (
    <>
      {segments.map((s, i) =>
        s.match ? <mark key={i}>{s.text}</mark> : <span key={i}>{s.text}</span>,
      )}
    </>
  );
}
