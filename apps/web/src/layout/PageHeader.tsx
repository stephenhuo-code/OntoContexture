import type { ReactNode } from "react";
import { Button, Tooltip } from "@contexture/ui";
import { AccountMenu } from "./AccountMenu";
import { zh } from "../i18n/zh-CN";
export function PageHeader({
  title,
  secondaryOpen,
  hasSecondary,
  toggle,
  heading,
  center,
}: {
  title: string;
  /** 006：数据资产页以顶栏面包屑代替标题（第一段为一级标题「数据资产」） */
  heading?: ReactNode;
  /** 006：数据资产页顶栏中间的搜索框（D3，只在本页出现） */
  center?: ReactNode;
  secondaryOpen: boolean;
  hasSecondary: boolean;
  toggle: () => void;
}) {
  const label = secondaryOpen ? zh.nav.collapse : zh.nav.expand;
  return (
    <header className="page-header">
      <div className="page-heading">
        {hasSecondary && (
          <Tooltip content={label}>
            <Button
              variant="ghost"
              aria-label={label}
              aria-expanded={secondaryOpen}
              aria-controls="secondary-navigation"
              onClick={toggle}
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                width="20"
                height="20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
              >
                <path d="M3 4h18v16H3ZM9 4v16m4-12 4 4-4 4" />
              </svg>
            </Button>
          </Tooltip>
        )}
        {heading ?? <h1>{title}</h1>}
      </div>
      {center}
      <AccountMenu />
    </header>
  );
}
