// Mock data for the prototype. Everything here will come from the backend later
// (see BACKEND_QUESTIONS.md for what the app needs from it).

export const AVATAR = { peach: "#F29E6D", sage: "#A9C9A4", sky: "#B9CFE6", honey: "#F5BE6B" };

export const DOGS = [
  {
    id: "bruno", name: "Bruno", pronoun: "he", initial: "B", color: AVATAR.peach,
    breed: "Labrador", age: "3 yrs", weight: "31 kg",
    score: 912, rank: 7, city: "Bucharest", streak: 12,
    success7d: 86, reaction: "0.9 s", successesToday: 16, treatsToday: 14, treatLimit: 35,
    week: [62, 68, 66, 72, 76, 80, 86],
    exercises: [
      { id: "down", name: "Down", stage: "learn", moments: 18, goal: 30, startedAgo: "4 days ago",
        schedule: "Daily, 10:00–17:00", limitNote: "max 10 treats · one every 30 min",
        caught: [["14:32", "Lay down by the couch"], ["12:05", "Lay down after playtime"], ["10:48", "Lay down by the window"]] },
      { id: "sit", name: "Sit", stage: "train", rate: 94, level: 5, detail: "Holds 2.5 s · one more level to master it" },
      { id: "stand", name: "Stand", stage: "train", rate: 88, level: 3, detail: "Holds 1.5 s" },
      { id: "stay", name: "Stay", stage: "next", detail: "Starts once he masters “Sit”" },
    ],
  },
  {
    id: "luna", name: "Luna", pronoun: "she", initial: "L", color: AVATAR.sage,
    breed: "Border Collie", age: "2 yrs", weight: "17 kg",
    score: 948, rank: 3, city: "Bucharest", streak: 21,
    success7d: 91, reaction: "0.7 s", successesToday: 12, treatsToday: 9, treatLimit: 24,
    week: [80, 78, 85, 83, 88, 91, 89],
    exercises: [
      { id: "paw", name: "Paw", stage: "learn", moments: 7, goal: 30, startedAgo: "2 days ago",
        schedule: "Weekends, 12:00–16:00", limitNote: "max 8 treats · one every 30 min",
        caught: [["11:20", "Gave her paw while begging"], ["09:02", "Lifted her paw at the door"]] },
      { id: "down", name: "Down", stage: "train", rate: 90, level: 4, detail: "Holds 2.0 s" },
      { id: "stay", name: "Stay", stage: "train", rate: 82, level: 3, detail: "Holds 6 s · goal 15 s" },
      { id: "sit", name: "Sit", stage: "mastered", rate: 98, level: 6, detail: "Mastered · quick refresher weekly" },
    ],
  },
  {
    id: "toby", name: "Toby", pronoun: "he", initial: "T", color: AVATAR.sky,
    breed: "Beagle", age: "8 mos", weight: "9 kg",
    score: 604, rank: 41, city: "Bucharest", streak: 5,
    success7d: 58, reaction: "1.8 s", successesToday: 5, treatsToday: 5, treatLimit: 18,
    week: [40, 44, 51, 49, 55, 58, 63],
    exercises: [
      { id: "sit", name: "Sit", stage: "learn", moments: 24, goal: 30, startedAgo: "6 days ago",
        schedule: "Mon–Fri, 09:00–18:00", limitNote: "max 12 treats · one every 30 min",
        caught: [["15:10", "Sat by the food bowl"], ["13:44", "Sat when the door opened"], ["10:02", "Sat in his bed"]] },
      { id: "down", name: "Down", stage: "next", detail: "Starts once he learns “Sit”" },
    ],
  },
];

export const WEEK_ALL = [66, 71, 69, 75, 78, 81, 84];
export const WEEK_DAYS = ["M", "T", "W", "T", "F", "S", "S"];

export const SCHEDULES = [
  { id: 1, dog: "bruno", type: "learn", title: "Bruno · Down", when: "Daily, 10:00–17:00", sessions: 1, max: 10, on: true },
  { id: 2, dog: "toby", type: "learn", title: "Toby · Sit", when: "Mon–Fri, 09:00–18:00", sessions: 1, max: 12, on: true },
  { id: 3, dog: "bruno", type: "train", title: "Bruno · Sit and Stand", when: "Daily, 08:00 and 18:30", sessions: 2, max: 10, on: true },
  { id: 4, dog: "luna", type: "train", title: "Luna · Down and Stay", when: "Daily, 18:30", sessions: 1, max: 10, on: true },
  { id: 5, dog: "luna", type: "learn", title: "Luna · Paw", when: "Weekends, 12:00–16:00", sessions: 1, max: 8, on: false },
];

const LB_DOGS = {
  max: ["Max", "German Shepherd", "Floreasca", "#B9CFE6"],
  bella: ["Bella", "Golden Retriever", "Cotroceni", "#F5BE6B"],
  rocky: ["Rocky", "Malinois", "Titan", "#A9C9A4"],
  coco: ["Coco", "Poodle", "Aviației", "#E3C4DD"],
  zara: ["Zara", "Vizsla", "Drumul Taberei", "#F2C3A0"],
  oscar: ["Oscar", "Corgi", "Dorobanți", "#BFDCD8"],
  bruno: ["Bruno", "Labrador", "Herăstrău", "#F29E6D"],
  kira: ["Kira", "Husky", "Militari", "#D6CBBE"],
  lola: ["Lola", "Jack Russell", "Berceni", "#F0B8B0"],
  ares: ["Ares", "Doberman", "Băneasa", "#C9B79F"],
};

const LB_CATS = {
  score: { label: "Good Boy Score", list: [["rocky", "988", "="], ["bella", "971", "+2"], ["max", "963", "-1"], ["coco", "955", "+1"], ["zara", "949", "-2"], ["oscar", "931", "+3"], ["bruno", "912", "+5"], ["kira", "904", "-1"], ["lola", "896", "="], ["ares", "887", "-4"]] },
  fast: { label: "Fastest", list: [["zara", "0.41 s", "+1"], ["rocky", "0.44 s", "-1"], ["oscar", "0.52 s", "+4"], ["bruno", "0.55 s", "+2"], ["bella", "0.58 s", "="], ["max", "0.61 s", "-2"], ["lola", "0.63 s", "+1"], ["coco", "0.70 s", "-3"], ["kira", "0.74 s", "="], ["ares", "0.81 s", "-1"]] },
  streak: { label: "Longest streak", list: [["max", "64 days", "="], ["coco", "51 days", "="], ["rocky", "47 days", "+1"], ["lola", "39 days", "-1"], ["bella", "33 days", "="], ["kira", "28 days", "+2"], ["ares", "21 days", "="], ["bruno", "12 days", "+1"], ["zara", "9 days", "-3"], ["oscar", "6 days", "="]] },
  rise: { label: "Most improved", list: [["oscar", "+142", "+9"], ["bruno", "+118", "+5"], ["lola", "+97", "+3"], ["bella", "+81", "+2"], ["kira", "+66", "="], ["coco", "+52", "+1"], ["zara", "+40", "-2"], ["rocky", "+31", "-1"], ["max", "+18", "-3"], ["ares", "+4", "-4"]] },
};

export const LB_SCOPES = [["area", "Neighborhood"], ["city", "City"], ["country", "Country"]];
export const LB_CATEGORIES = Object.entries(LB_CATS).map(([id, c]) => ({ id, label: c.label }));

/** Ranked entries for a category (scope is cosmetic in the mock). */
export function leaderboard(category) {
  return LB_CATS[category].list.map(([id, value, move], i) => {
    const [name, breed, area, color] = LB_DOGS[id];
    return { id, rank: i + 1, name, breed, area, color, value, move, mine: id === "bruno" };
  });
}
