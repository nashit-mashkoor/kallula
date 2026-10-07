import { useEffect } from "react";

import { apiUrl } from "../api/client";

export function useAccountStream(onResourceChanged: () => void) {
  useEffect(() => {
    const source = new EventSource(apiUrl("/api/v1/stream"));
    source.addEventListener("resource_changed", () => onResourceChanged());
    return () => source.close();
  }, [onResourceChanged]);
}
