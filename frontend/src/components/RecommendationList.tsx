import type { Recommendation } from "../api/types";
import type { DriveState, GuideState } from "../hooks/useRecommend";
import RecommendationCard from "./RecommendationCard";

interface Props {
  recommendations: Recommendation[];
  note: string | null;
  guides: Record<string, GuideState>;
  drives: Record<string, DriveState>;
  hasOrigin: boolean;
  onRetryGuide: (cityId: string) => void;
  onRequestDrive: (cityId: string) => void;
  onRetryDrive: (cityId: string) => void;
  onCancelDrive: (cityId: string) => void;
}

export default function RecommendationList({
  recommendations,
  note,
  guides,
  drives,
  hasOrigin,
  onRetryGuide,
  onRequestDrive,
  onRetryDrive,
  onCancelDrive,
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
          drive={drives[rec.city.id]}
          hasOrigin={hasOrigin}
          onRetryGuide={() => onRetryGuide(rec.city.id)}
          onRequestDrive={() => onRequestDrive(rec.city.id)}
          onRetryDrive={() => onRetryDrive(rec.city.id)}
          onCancelDrive={() => onCancelDrive(rec.city.id)}
        />
      ))}
    </section>
  );
}
