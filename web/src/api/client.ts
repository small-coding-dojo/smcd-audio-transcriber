import { httpClient } from "./http";
import { mockClient } from "./mock";

// The backend is mocked by default. Run with VITE_API=real to use the actual service.
export const client = import.meta.env.VITE_API === "real" ? httpClient : mockClient;
