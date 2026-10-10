import { useCallback, useRef, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { GuideResponse, RecommendRequestBody, Recommendation } from "../api/types";

export interface GuideState {
  status: "loading" | "done" | "error";
  data?: GuideResponse;
  error?: string;
}

type Phase = "idle" | "recommending" | "done" | "failed";

/**
 * 推荐 + 攻略的完整状态机:
 * 提交推荐 → 拿到 1-3 个推荐后并行请求各城市攻略(单城失败不影响其他)。
 */
export function useRecommend() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [guides, setGuides] = useState<Record<string, GuideState>>({});
  const guideCache = useRef(new Map<string, GuideResponse>());
  // 每个推荐城市实际安排的行程区间(推荐结果给出,不一定是用户时间窗口的全长)
  const recMeta = useRef<Record<string, { start: string; end: string; tags?: string[] }>>({});

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

  const submit = useCallback(
    async (body: RecommendRequestBody) => {
      setPhase("recommending");
      setError(null);
      setNote(null);
      setGuides({});
      setRecommendations([]);
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
  }, []);

  return { phase, recommendations, note, error, guides, submit, retryGuide, reset };
}
