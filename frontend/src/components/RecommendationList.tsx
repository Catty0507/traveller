import type { Recommendation } from "../api/types";
import type { GuideState } from "../hooks/useRecommend";
import RecommendationCard from "./RecommendationCard";

interface Props {
  recommendations: Recommendation[];
  note: string | null;
  guides: Record<string, GuideState>;
  onRetryGuide: (cityId: string) => void;
}

export default function RecommendationList({
  recommendations,
  note,
  guides,
  onRetryGuide,
}: Props) {
  return (
    <section className="space-y-6">
      {note && (
        <div className="rounded-2xl bg-amber-50 px-5 py-3 text-sm text-amber-700 ring-1 ring-amber-100">
          🌈 {note}
        </div>
      )}
      {recommendations.map((rec) => (
        <RecommendationCard
          key={rec.city.id}
          rec={rec}
          guide={guides[rec.city.id]}
          onRetryGuide={() => onRetryGuide(rec.city.id)}
        />
      ))}
    </section>
  );
}
