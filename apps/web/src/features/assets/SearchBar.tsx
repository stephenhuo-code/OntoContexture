import { useEffect, useRef, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";
import type { EntityType, Suggestion } from "@contexture/ts-api";
import { useAssetsCriteria } from "./criteria";
import { detailTarget } from "./links";
import { typeLabel } from "./labels";
import { useScopeOptions, useSuggestions } from "./queries";

const DEBOUNCE_MS = 400; // OM GlobalSearchBar.tsx:133

/** 数据资产页顶栏搜索框（D3）：搜索范围（D4）、输入建议（FR-005）、回车按相关性搜索（FR-004）。 */
export function SearchBar() {
  const { criteria, dispatch } = useAssetsCriteria();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [text, setText] = useState(criteria.keyword);
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const blurTimer = useRef<number | undefined>(undefined);
  const scopes = useScopeOptions();
  const suggestions = useSuggestions(open ? debounced : "", criteria.scope);

  useEffect(() => setText(criteria.keyword), [criteria.keyword]);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(text.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [text]);

  const toExplore = () => {
    if (pathname !== "/assets") navigate("/assets");
  };
  const search = (keyword: string) => {
    dispatch({ type: "keyword", keyword });
    dispatch({ type: "entityType", entityType: null });
    if (keyword) dispatch({ type: "sort", field: "relevance", order: "desc" });
    setOpen(false);
    toExplore();
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    search(text);
  };
  const pick = (s: Suggestion) => {
    const target = detailTarget(s.ref, s.parentTable, s.columnName);
    setOpen(false);
    if (target)
      navigate(target.to, target.state ? { state: target.state } : undefined);
    else {
      setText(s.label);
      search(s.label);
    }
  };

  const groups =
    suggestions.status === "ready"
      ? suggestions.data.groups.filter((g) => g.items.length)
      : [];
  return (
    <div className="asset-search">
      <form className="asset-search__box" role="search" onSubmit={submit}>
        <select
          aria-label="搜索范围"
          value={criteria.scope ?? ""}
          onChange={(e) =>
            dispatch({
              type: "scope",
              scope: (e.target.value || null) as EntityType | null,
            })
          }
        >
          <option value="">全部资产</option>
          {scopes.map((t) => (
            <option key={t} value={t}>
              {typeLabel(t)}
            </option>
          ))}
        </select>
        <input
          type="search"
          aria-label="搜索数据资产"
          placeholder="搜索表名、字段名、业务名称或描述"
          value={text}
          maxLength={200}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            // 清空搜索框（删光或点框内 ✕）即退出关键词搜索，左栏回到浏览树；
            // 与 OM GlobalSearchBar.handleClear 一致，排序、位置与快速筛选保持不变
            if (!e.target.value.trim() && criteria.keyword) {
              dispatch({ type: "keyword", keyword: "" });
              dispatch({ type: "entityType", entityType: null });
            }
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => setOpen(false), 150);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
          }}
        />
      </form>
      {open && debounced && groups.length > 0 && (
        <div
          role="listbox"
          aria-label="输入建议"
          className="asset-search__suggestions"
          onMouseDown={() => window.clearTimeout(blurTimer.current)}
        >
          {groups.map((g) => (
            <div
              key={g.entityType}
              role="group"
              aria-label={typeLabel(g.entityType)}
            >
              <div className="asset-search__group">
                {typeLabel(g.entityType)}
              </div>
              {g.items.map((s) => (
                <div
                  key={`${s.ref.entityType}:${s.ref.fqn}`}
                  role="option"
                  aria-selected={false}
                  tabIndex={-1}
                  className="asset-search__option"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => pick(s)}
                >
                  <span>{s.label}</span>
                  <small>{s.location}</small>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
