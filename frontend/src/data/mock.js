// UI constants and styling helpers (data is persisted in the database via IPetRepository).

export const AVATAR = { peach: "#F29E6D", sage: "#A9C9A4", sky: "#B9CFE6", honey: "#F5BE6B" };

export const DOG_PHOTO_PRESETS = [
  "/dogs/preset_1.jpg",
  "/dogs/preset_2.jpg",
  "/dogs/preset_3.jpg",
  "/dogs/preset_4.jpg",
  "/dogs/bella.jpg",
  "/dogs/rocky.jpg",
];

export const WEEK_ALL = [66, 71, 69, 75, 78, 81, 84];
export const WEEK_DAYS = ["M", "T", "W", "T", "F", "S", "S"];

export const LB_SCOPES = [
  ["area", "Neighborhood"],
  ["city", "City"],
  ["country", "Country"],
];

export const LB_CATEGORIES = [
  { id: "score", label: "Good Boy Score" },
  { id: "fast", label: "Fastest" },
  { id: "streak", label: "Longest streak" },
  { id: "rise", label: "Most improved" },
];
