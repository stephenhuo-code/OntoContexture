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
  | { status: "authenticated"; user: CurrentUser }
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
