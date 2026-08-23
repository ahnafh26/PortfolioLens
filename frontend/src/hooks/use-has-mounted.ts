import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

// avoids the useEffect+setState pattern, no extra render
export function useHasMounted(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
