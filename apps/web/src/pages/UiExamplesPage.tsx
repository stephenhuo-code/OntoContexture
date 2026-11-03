import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  Button,
  PageState,
  Panel,
  StatusBadge,
  TextInput,
  type PageStateKind,
} from "@contexture/ui";
import { zh } from "../i18n/zh-CN";
const t = zh.examples;
const kinds = ["loading", "empty", "error", "forbidden", "not_open"] as const;
function SampleContent() {
  const [ready, setReady] = useState(false);
  return (
    <Panel title={t.sample} aria-label={t.sample}>
      {ready ? (
        <p>{t.sampleReady}</p>
      ) : (
        <PageState
          kind="empty"
          title={t.sampleEmpty}
          description={t.stateDescription}
          actionLabel={t.sampleAction}
          action={() => setReady(true)}
        />
      )}
    </Panel>
  );
}
export default function UiExamplesPage() {
  const navigate = useNavigate();
  const [kind, setKind] = useState<PageStateKind | "ready">("empty");
  const [fail, setFail] = useState(false);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => () => clearTimeout(timer.current), []);
  function show(next: PageStateKind) {
    clearTimeout(timer.current);
    setBusy(false);
    setKind(next);
  }
  function retry() {
    if (busy) return;
    setBusy(true);
    timer.current = setTimeout(() => {
      setBusy(false);
      setKind(fail ? "error" : "ready");
    }, 300);
  }
  const title =
    kind === "loading"
      ? t.loadingTitle
      : kind === "empty"
        ? t.emptyTitle
        : kind === "error"
          ? t.errorTitle
          : kind === "forbidden"
            ? t.forbiddenTitle
            : t.notOpenTitle;
  return (
    <div className="examples-page">
      <p className="example-notice">{t.notice}</p>
      <Panel title={t.primitives}>
        <div className="example-buttons">
          <Button>{t.primary}</Button>
          <Button variant="secondary">{t.secondary}</Button>
          <Button disabled>{t.disabled}</Button>
          <Button busy>{t.busy}</Button>
          <StatusBadge>{t.neutral}</StatusBadge>
          <StatusBadge tone="positive">{t.positive}</StatusBadge>
          <StatusBadge tone="warning">{t.warning}</StatusBadge>
        </div>
        <TextInput label={t.input} defaultValue={t.longText.repeat(8)} />
        <p className="long-example">{t.longText.repeat(12)}</p>
      </Panel>
      <Panel title={t.states} aria-label={t.states}>
        <div className="example-buttons">
          {kinds.map((k) => (
            <Button key={k} variant="secondary" onClick={() => show(k)}>
              {t[k]}
            </Button>
          ))}
        </div>
        <label className="example-checkbox">
          <input
            type="checkbox"
            checked={fail}
            onChange={(e) => setFail(e.target.checked)}
          />
          {t.failAgain}
        </label>
        {kind === "ready" ? (
          <p role="status">{t.ready}</p>
        ) : (
          <PageState
            kind={kind}
            title={title}
            description={t.stateDescription}
            busy={busy}
            actionLabel={
              kind === "error"
                ? zh.session.retry
                : kind === "empty"
                  ? t.load
                  : kind === "loading"
                    ? undefined
                    : zh.home
            }
            action={
              kind === "error"
                ? retry
                : kind === "empty"
                  ? () => setKind("ready")
                  : kind === "loading"
                    ? undefined
                    : () => navigate("/home")
            }
          />
        )}
        {kind === "loading" && (
          <Button variant="secondary" onClick={() => setKind("ready")}>
            {t.end}
          </Button>
        )}
      </Panel>
      <SampleContent />
    </div>
  );
}
