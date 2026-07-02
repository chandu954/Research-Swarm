import { vi } from "vitest";

export function mockApi() {
  const fetchMock = vi.fn();
  global.fetch = fetchMock;
  return fetchMock;
}

export function mockApiResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  };
}
