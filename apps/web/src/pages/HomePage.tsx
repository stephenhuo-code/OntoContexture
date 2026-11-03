import { Panel, StatusBadge } from "@contexture/ui";
import { useSession } from "../auth/SessionProvider";
import { zh } from "../i18n/zh-CN";
export function HomePage() {
  const { state } = useSession();
  if (state.status !== "authenticated") return null;
  return (
    <div className="home-page">
      <h2 className="home-greeting">
        {zh.greeting(state.user.display_name || state.user.user_id)}
      </h2>
      <p>{zh.homeDescription}</p>
      <div className="metrics-grid">
        {zh.metrics.map((label, index) => (
          <Panel title={label} key={label}>
            <div
              className={`metric-mark metric-mark-${index}`}
              aria-hidden="true"
            >
              <span>◇</span>
            </div>
            <StatusBadge>{zh.notConnected}</StatusBadge>
          </Panel>
        ))}
      </div>
      <div className="home-panels">
        <Panel title={zh.todo}>
          <div className="home-empty">
            <span aria-hidden="true" className="empty-symbol">
              ☷
            </span>
            <StatusBadge>{zh.notOpen}</StatusBadge>
            <p>{zh.todoDescription}</p>
          </div>
        </Panel>
        <Panel title={zh.recent}>
          <div className="home-empty">
            <span aria-hidden="true" className="empty-symbol">
              ▤
            </span>
            <StatusBadge>{zh.notOpen}</StatusBadge>
            <p>{zh.recentDescription}</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
