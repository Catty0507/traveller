export type Mode = "cities" | "tags";

export interface City {
  id: string;
  name_zh: string;
  name_en: string;
  country: string;
  region: string;
  lat: number;
  lon: number;
  timezone: string;
  summary: string;
  suggested_days: number;
  tags: string[];
  cover_color: string;
}

export interface Tag {
  id: string;
  label: string;
  emoji: string;
}

export interface DailyWeather {
  date: string;
  weather_code: number;
  desc: string;
  emoji: string;
  t_max: number;
  t_min: number;
  rain_prob: number | null;
  precip_mm: number;
}

export interface WeatherSummary {
  summary_text: string;
  avg_t_max: number;
  avg_t_min: number;
  rainy_days: number;
  total_days: number;
  days: DailyWeather[];
}

export interface Origin {
  lat: number;
  lon: number;
  name?: string | null;
}

export interface Recommendation {
  rank: number;
  city: City;
  weather: WeatherSummary;
  reason: string;
  warning: string | null;
  matched_tags: string[];
  distance_km?: number | null;
  trip_start: string; // 实际安排的行程区间(时间窗口内的一段)
  trip_end: string;
}

export interface RecommendResponse {
  mode: Mode;
  note: string | null;
  recommendations: Recommendation[];
}

export interface RecommendRequestBody {
  mode: Mode;
  start_date: string;
  end_date: string;
  city_ids?: string[];
  tags?: string[];
  origin?: Origin;
}

export interface GuideRequestBody {
  city_id: string;
  start_date: string;
  end_date: string;
  user_tags?: string[];
}

export interface Attraction {
  name: string;
  highlight: string;
  duration: string;
  tip: string;
}

export interface DayPlan {
  day: number;
  date: string;
  title: string;
  items: string[];
}

export interface FoodItem {
  name: string;
  desc: string;
}

export interface TipItem {
  category: string;
  text: string;
}

export interface GuideData {
  overview: string;
  attractions: Attraction[];
  daily_plan: DayPlan[];
  food: FoodItem[];
  tips: TipItem[];
}

export interface GuideResponse {
  city_id: string;
  city_name_zh: string;
  start_date: string;
  end_date: string;
  weather_brief: string;
  guide: GuideData;
}
