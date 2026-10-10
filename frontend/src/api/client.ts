import type {
  City,
  GuideRequestBody,
  GuideResponse,
  RecommendRequestBody,
  RecommendResponse,
  Tag,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("网络异常,请确认后端服务已启动(端口 8000)", 0);
  }
  if (!res.ok) {
    let detail = `请求失败(${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // 保留默认错误信息
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getCities: () => request<{ total: number; cities: City[] }>("/api/cities"),
  searchCities: (q: string) =>
    request<{ total: number; cities: City[] }>(
      `/api/cities/search?q=${encodeURIComponent(q)}`
    ),
  getTags: () => request<{ tags: Tag[] }>("/api/tags"),
  recommend: (body: RecommendRequestBody) =>
    request<RecommendResponse>("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  guide: (body: GuideRequestBody) =>
    request<GuideResponse>("/api/guide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return "发生未知错误,请重试";
}
