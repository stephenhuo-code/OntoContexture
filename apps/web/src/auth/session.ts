import type { Me } from "@contexture/ts-api";
import type { ApiFailure } from "../api";
export interface CurrentUser {
  tenant_id: string;
  user_id: string;
  display_name: string | null;
  roles: string[];
}
export type SessionView =
  | { status: "checking" }
  /** rechecking：切回窗口等场景的后台身份核验进行中；页面保留但不可操作 */
  | { status: "authenticated"; user: CurrentUser; rechecking: boolean }
  | { status: "anonymous" }
  | { status: "forbidden" }
  | { status: "unavailable"; error: ApiFailure };
export function normalizeUser(me: Me): CurrentUser {
  return {
    ...me,
    display_name: me.display_name ?? null,
    roles: me.roles ?? [],
  };
}
