import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiFailure, loadMe, logout as endSession } from "../api";
import { normalizeUser, type SessionView } from "./session";

interface SessionContextValue {
  state: SessionView;
  recheck: () => void;
  logout: () => Promise<void>;
  logoutPending: boolean;
  logoutError: ApiFailure | null;
}
const Context = createContext<SessionContextValue | null>(null);
export function useSession() {
  const value = useContext(Context);
  if (!value) throw Error("SessionProvider required");
  return value;
}
function Controller({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [anonymous, setAnonymous] = useState(false);
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState<ApiFailure | null>(null);
  const busy = useRef(false);
  const previousUser = useRef<string | null>(null);
  const me = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => loadMe(signal),
    enabled: !anonymous,
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  let state: SessionView;
  if (anonymous) state = { status: "anonymous" };
  else if (me.isPending || (me.isFetching && !me.isSuccess))
    state = { status: "checking" };
  else if (me.isError) {
    const error = me.error instanceof ApiFailure ? me.error : new ApiFailure(0);
    state =
      error.status === 401
        ? { status: "anonymous" }
        : error.status === 403
          ? { status: "forbidden" }
          : { status: "unavailable", error };
  } else
    // 已登录时的重新核验在后台进行：保留页面状态，核验结果为退出 / 无权限时再切换（005 负责人确认）
    state = {
      status: "authenticated",
      user: normalizeUser(me.data),
      rechecking: me.isFetching,
    };
  const userId = state.status === "authenticated" ? state.user.user_id : null;
  useEffect(() => {
    if (previousUser.current && previousUser.current !== userId) {
      void client.cancelQueries({
        predicate: (q) => q.queryKey[0] !== "session",
      });
      client.removeQueries({ predicate: (q) => q.queryKey[0] !== "session" });
    }
    previousUser.current = userId;
  }, [client, userId]);
  const recheck = useCallback(() => {
    if (!anonymous && !busy.current)
      void client.refetchQueries({ queryKey: ["session"], exact: true });
  }, [anonymous, client]);
  useEffect(() => {
    const visible = () => {
      if (document.visibilityState === "visible") recheck();
    };
    window.addEventListener("focus", recheck);
    window.addEventListener("pageshow", recheck);
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.removeEventListener("focus", recheck);
      window.removeEventListener("pageshow", recheck);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [recheck]);
  const logout = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setLogoutPending(true);
    setLogoutError(null);
    try {
      await endSession();
      setAnonymous(true);
      await client.cancelQueries();
      client.clear();
    } catch (error) {
      setLogoutError(error instanceof ApiFailure ? error : new ApiFailure(0));
    } finally {
      busy.current = false;
      setLogoutPending(false);
    }
  }, [client]);
  return (
    <Context.Provider
      value={{ state, recheck, logout, logoutPending, logoutError }}
    >
      {children}
    </Context.Provider>
  );
}
export function SessionProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient());
  useEffect(() => () => client.clear(), [client]);
  return (
    <QueryClientProvider client={client}>
      <Controller>{children}</Controller>
    </QueryClientProvider>
  );
}
