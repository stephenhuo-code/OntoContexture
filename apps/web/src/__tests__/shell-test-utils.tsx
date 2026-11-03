import { render, screen } from "@testing-library/react";
import { MemoryRouter, useNavigate } from "react-router";
import { vi } from "vitest";
import { App } from "../App";

export function stubIdentity(name = "真实工程师") {
  const paths: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      paths.push(new URL(request.url, "http://localhost").pathname);
      return new Response(
        JSON.stringify({
          tenant_id: "local",
          user_id: "subject-1",
          display_name: name,
          roles: ["ai-engineer"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }),
  );
  return paths;
}
function HistoryButtons() {
  const navigate = useNavigate();
  return (
    <aside aria-label="测试历史">
      <button onClick={() => navigate(-1)}>测试后退</button>
      <button onClick={() => navigate(1)}>测试前进</button>
    </aside>
  );
}
export async function openShell(path = "/home", history = false) {
  const view = render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      {history && <HistoryButtons />}
    </MemoryRouter>,
  );
  await screen.findByLabelText(/当前账号：/);
  return view;
}
