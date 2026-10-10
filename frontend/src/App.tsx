import { useEffect, useState } from "react";
import { api, errorMessage } from "./api/client";
import type { City, Tag } from "./api/types";
import Hero from "./components/Hero";
import InputCard from "./components/InputCard";
import RecommendationList from "./components/RecommendationList";
import { useRecommend } from "./hooks/useRecommend";

export default function App() {
  const [cities, setCities] = useState<City[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const rec = useRecommend();

  useEffect(() => {
    Promise.all([api.getCities(), api.getTags()])
      .then(([citiesResp, tagsResp]) => {
        setCities(citiesResp.cities);
        setTags(tagsResp.tags);
      })
      .catch((e) => setLoadError(errorMessage(e)));
  }, []);

  return (
    <div className="relative min-h-screen bg-gradient-to-b from-sky-100/70 via-sky-50/40 to-white">
      {/* 背景装饰光斑,让纯色页面更柔和 */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-24 -top-32 h-80 w-80 rounded-full bg-sky-200/50 blur-3xl" />
        <div className="absolute -right-32 top-1/2 h-96 w-96 rounded-full bg-amber-100/60 blur-3xl" />
        <div className="absolute bottom-0 left-1/4 h-72 w-72 rounded-full bg-rose-100/40 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-5xl px-4 py-6 sm:px-6 md:py-10">
        <Hero />

        <div className="relative z-10 -mt-12 md:-mt-16">
          {loadError ? (
            <div className="rounded-2xl bg-rose-50 px-5 py-4 text-sm text-rose-600 ring-1 ring-rose-100">
              {loadError}
            </div>
          ) : (
            <InputCard
              cities={cities}
              tags={tags}
              submitting={rec.phase === "recommending"}
              onSubmit={rec.submit}
            />
          )}
        </div>

        <div className="mt-10 space-y-6">
          {rec.phase === "recommending" && (
            <div className="space-y-4">
              {[0, 1].map((i) => (
                <div
                  key={i}
                  className="h-48 animate-pulse rounded-3xl bg-white/80 ring-1 ring-slate-100"
                />
              ))}
              <p className="text-center text-xs text-slate-400">
                正在对比各地天气,挑出最合适的…
              </p>
            </div>
          )}

          {rec.phase === "failed" && (
            <div className="rounded-2xl bg-rose-50 px-5 py-4 text-sm text-rose-600 ring-1 ring-rose-100">
              😢 {rec.error}
            </div>
          )}

          {rec.phase === "done" && (
            <RecommendationList
              recommendations={rec.recommendations}
              note={rec.note}
              guides={rec.guides}
              drives={rec.drives}
              hasOrigin={rec.hasOrigin}
              onRetryGuide={rec.retryGuide}
              onRequestDrive={rec.requestDrive}
              onRetryDrive={rec.retryDrive}
              onCancelDrive={rec.cancelDrive}
            />
          )}
        </div>

        <footer className="mt-14 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-xs text-slate-400">
          <span>🌤 天气数据 Open-Meteo</span>
          <span className="text-slate-300">·</span>
          <span>攻略内容仅供参考</span>
          <span className="text-slate-300">·</span>
          <span>祝旅途愉快</span>
        </footer>
      </div>
    </div>
  );
}
