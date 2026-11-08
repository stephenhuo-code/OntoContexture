// 导航与目录图标（内联 SVG，线性风格；2026-11-08 负责人按附图调整）
const ICONS: Record<string, string[]> = {
  new: [
    "M7 3h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7a4 4 0 0 1 4-4Z",
    "M12 8v8",
    "M8 12h8",
  ],
  home: ["M3 10.5 12 3l9 7.5", "M5 9.5V20h5v-6h4v6h5V9.5"],
  assets: [
    "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Z",
    "M4 6v12c0 1.7 3.6 3 8 3",
    "M20 6v5",
    "M4 12c0 1.7 3.6 3 8 3",
    "M17.5 20.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "m19.7 19.7 1.8 1.8",
  ],
  agents: [
    "M10 3l1.6 4.4L16 9l-4.4 1.6L10 15l-1.6-4.4L4 9l4.4-1.6Z",
    "M18 14l.8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8Z",
    "M18 3v3M16.5 4.5h3",
  ],
  search: ["M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Z", "m16 16 5 5"],
  database: [
    "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Z",
    "M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6",
    "M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  ],
  schema: ["m12 3 9 5-9 5-9-5Z", "m3 13 9 5 9-5"],
  table: [
    "M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z",
    "M4 10h16",
    "M10 4v16",
  ],
  chevron: ["m9 6 6 6-6 6"],
  // 品牌：两条经线穿过两条纬线（织）
  brand: [
    "M9 4v16",
    "M15 4v16",
    "M3 9.5c3-2.6 6-2.6 9 0s6 2.6 9 0",
    "M3 14.5c3-2.6 6-2.6 9 0s6 2.6 9 0",
  ],
  overview: ["M4 4h7v7H4Z", "M13 4h7v4h-7Z", "M13 10h7v10h-7Z", "M4 13h7v7H4Z"],
  approval: [
    "M9 11l2 2 4-4",
    "M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z",
  ],
  "module-asset": [
    "M5 4h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z",
    "M17 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M7 20a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M15 14h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Z",
  ],
};

export function NavIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      data-icon={name}
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {(ICONS[name] ?? []).map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
