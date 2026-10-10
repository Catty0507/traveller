import { useCallback, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type {
  DriveResponse,
  GuideResponse,
  Origin,
  RecommendRequestBody,
  Recommendation,
} from "../api/types";

export interface GuideState {
  status: "loading" | "done" | "error";
  data?: GuideResponse;
  error?: string;
}

export interface DriveState {
  status: "loading" | "done" | "error";
  data?: DriveResponse;
  error?: string;
}

// 每个推荐城市记录的上下文:实际行程区间 + 原始空闲窗口 + 出发地(自驾规划要用)
interface RecMeta {
  start: string;
  end: string;
  tags?: string[];
  origin?: Origin;
  windowStart: string;
  windowEnd: string;
}

type Phase = "idle" | "recommending" | "done" | "failed";

/**
 * 推荐 + 攻略的完整状态机:
 * 提交推荐 → 拿到 1-3 个推荐后并行请求各城市攻略(单城失败不影响其他);
 * 「我要自驾」按需触发单城自驾规划。
 */
export function useRecommend() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guides, setGuides] = useState<Record<string, GuideState>>({});
  const [drives, setDrives] = useState<Record<string, DriveState>>({});
  const [hasOrigin, setHasOrigin] = useState(false);
  const guideCache = useRef(new Map<string, GuideResponse>());
  const driveCache = useRef(new Map<string, DriveResponse>());
  const recMeta = useRef<Record<string, RecMeta>>({});

  const loadGuide = useCallback(
    async (cityId: string, start: string, end: string, tags?: string[]) => {
      const cacheKey = `${cityId}|${start}|${end}`;
      const cached = guideCache.current.get(cacheKey);
      if (cached) {
        setGuides((prev) => ({ ...prev, [cityId]: { status: "done", data: cached } }));
        return;
      }
      setGuides((prev) => ({ ...prev, [cityId]: { status: "loading" } }));
      try {
        const data = await api.guide({
          city_id: cityId,
          start_date: start,
          end_date: end,
          user_tags: tags,
        });
        guideCache.current.set(cacheKey, data);
        setGuides((prev) => ({ ...prev, [cityId]: { status: "done", data } }));
      } catch (e) {
        setGuides((prev) => ({ ...prev, [cityId]: { status: "error", error: errorMessage(e) } }));
      }
    },
    []
  );

  const loadDrive = useCallback(async (cityId: string) => {
    const meta = recMeta.current[cityId];
    if (!meta?.origin) return;
    const cacheKey = `${cityId}|${meta.windowStart}|${meta.windowEnd}|${meta.origin.lat.toFixed(3)},${meta.origin.lon.toFixed(3)}`;
    const cached = driveCache.current.get(cacheKey);
    if (cached) {
      setDrives((prev) => ({ ...prev, [cityId]: { status: "done", data: cached } }));
      return;
    }
    setDrives((prev) => ({ ...prev, [cityId]: { status: "loading" } }));
    try {
      const data = await api.drive({
        city_id: cityId,
        start_date: meta.windowStart,
        end_date: meta.windowEnd,
        trip_start: meta.start,
        trip_end: meta.end,
        origin: meta.origin,
        user_tags: meta.tags,
      });
      driveCache.current.set(cacheKey, data);
      setDrives((prev) => ({ ...prev, [cityId]: { status: "done", data } }));
    } catch (e) {
      setDrives((prev) => ({ ...prev, [cityId]: { status: "error", error: errorMessage(e) } }));
    }
  }, []);

  const requestDrive = useCallback(
    (cityId: string) => {
      if (!recMeta.current[cityId]?.origin) return; // 按钮在无出发地时应为禁用态,这里兜底
      void loadDrive(cityId);
    },
    [loadDrive]
  );

  const retryDrive = useCallback(
    (cityId: string) => {
      void loadDrive(cityId);
    },
    [loadDrive]
  );

  // 取消自驾模式:隐藏自驾方案、恢复原攻略。结果仍留在缓存里,再次点击秒开不重新请求
  const cancelDrive = useCallback((cityId: string) => {
    setDrives((prev) => {
      const next = { ...prev };
      delete next[cityId];
      return next;
    });
  }, []);

  const submit = useCallback(
    async (body: RecommendRequestBody) => {
      setPhase("recommending");
      setError(null);
      setNote(null);
      setGuides({});
      setDrives({});
      setRecommendations([]);
      setHasOrigin(Boolean(body.origin));
      try {
        const resp = await api.recommend(body);
        setRecommendations(resp.recommendations);
        setNote(resp.note);
        setPhase("done");
        recMeta.current = {};
        resp.recommendations.forEach((rec) => {
          recMeta.current[rec.city.id] = {
            start: rec.trip_start,
            end: rec.trip_end,
            tags: body.tags,
            origin: body.origin,
            windowStart: body.start_date,
            windowEnd: body.end_date,
          };
          void loadGuide(rec.city.id, rec.trip_start, rec.trip_end, body.tags);
        });
      } catch (e) {
        setError(errorMessage(e));
        setPhase("failed");
      }
    },
    [loadGuide]
  );

  const retryGuide = useCallback(
    (cityId: string) => {
      const meta = recMeta.current[cityId];
      if (meta) void loadGuide(cityId, meta.start, meta.end, meta.tags);
    },
    [loadGuide]
  );

  const reset = useCallback(() => {
    setPhase("idle");
    setRecommendations([]);
    setNote(null);
    setError(null);
    setGuides({});
    setDrives({});
    setHasOrigin(false);
  }, []);

  return {
    phase,
    recommendations,
    note,
    error,
    guides,
    drives,
    hasOrigin,
    submit,
    retryGuide,
    requestDrive,
    retryDrive,
    cancelDrive,
    reset,
  };
}
