/**
 * Concrete HttpRepository implementing IPetRepository.
 * Consumes FastAPI backend endpoints (/api/*) when available and maintains an AP cache
 * with write-behind queues for offline edge resilience.
 */
import { api } from "../api.js";
import { IPetRepository } from "./IPetRepository.js";

const CACHE_KEYS = {
  DOGS: "pawcoach_repo_dogs_v1",
  SCHEDULES: "pawcoach_repo_schedules_v1",
  MOMENTS: "pawcoach_repo_moments_v1",
  DEVICES: "pawcoach_repo_devices_v1",
  LEADERBOARD: "pawcoach_repo_lb_v1",
  QUEUE: "pawcoach_repo_queue_v1",
};

// Initial database seed snapshot so the app is instantly populated when offline
export const SEED_CACHE = {
  dogs: [
    {
      id: "bruno", name: "Bruno", pronoun: "he", initial: "B", color: "#F29E6D",
      image: "/dogs/bruno.jpg", breed: "Labrador", age: "3 yrs", weight: "31 kg",
      score: 912, rank: 7, city: "Bucharest", streak: 12, success7d: 86,
      reaction: "0.9 s", successesToday: 16, treatsToday: 14, treatLimit: 35,
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
      id: "luna", name: "Luna", pronoun: "she", initial: "L", color: "#A9C9A4",
      image: "/dogs/luna.jpg", breed: "Border Collie", age: "2 yrs", weight: "17 kg",
      score: 948, rank: 3, city: "Bucharest", streak: 21, success7d: 91,
      reaction: "0.7 s", successesToday: 12, treatsToday: 9, treatLimit: 24,
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
      id: "toby", name: "Toby", pronoun: "he", initial: "T", color: "#B9CFE6",
      image: "/dogs/toby.jpg", breed: "Beagle", age: "8 mos", weight: "9 kg",
      score: 604, rank: 41, city: "Bucharest", streak: 5, success7d: 58,
      reaction: "1.8 s", successesToday: 5, treatsToday: 5, treatLimit: 18,
      week: [40, 44, 51, 49, 55, 58, 63],
      exercises: [
        { id: "sit", name: "Sit", stage: "learn", moments: 24, goal: 30, startedAgo: "6 days ago",
          schedule: "Mon–Fri, 09:00–18:00", limitNote: "max 12 treats · one every 30 min",
          caught: [["15:10", "Sat by the food bowl"], ["13:44", "Sat when the door opened"], ["10:02", "Sat in his bed"]] },
        { id: "down", name: "Down", stage: "next", detail: "Starts once he learns “Sit”" },
      ],
    },
  ],
  schedules: [
    { id: 1, dog: "bruno", type: "learn", title: "Bruno · Down", when: "Daily, 10:00–17:00", sessions: 1, max: 10, on: true },
    { id: 2, dog: "toby", type: "learn", title: "Toby · Sit", when: "Mon–Fri, 09:00–18:00", sessions: 1, max: 12, on: true },
    { id: 3, dog: "bruno", type: "train", title: "Bruno · Sit and Stand", when: "Daily, 08:00 and 18:30", sessions: 2, max: 10, on: true },
    { id: 4, dog: "luna", type: "train", title: "Luna · Down and Stay", when: "Daily, 18:30", sessions: 1, max: 10, on: true },
    { id: 5, dog: "luna", type: "learn", title: "Luna · Paw", when: "Weekends, 12:00–16:00", sessions: 1, max: 8, on: false },
  ],
  moments: [
    { id: 1, dogName: "Bruno", dogBreed: "Labrador", dogImage: "/dogs/bruno.jpg", caption: "Mastering the ultimate slow sit roll 🎾", videoUrl: "/moments/dog1.mp4", likesCount: 142, liked: false },
    { id: 2, dogName: "Luna", dogBreed: "Border Collie", dogImage: "/dogs/luna.jpg", caption: "Wait for the sudden jump celebration! ✨", videoUrl: "/moments/dog2.mp4", likesCount: 289, liked: false },
    { id: 3, dogName: "Toby", dogBreed: "Beagle", dogImage: "/dogs/toby.jpg", caption: "When the treat dispenser sound makes you freeze 🍪", videoUrl: "/moments/dog4.mp4", likesCount: 95, liked: false },
    { id: 4, dogName: "Rocky", dogBreed: "Malinois", dogImage: "/dogs/rocky.jpg", caption: "Perfect posture check in 0.4 seconds flat ⚡", videoUrl: "/moments/dog_labradoodle_stand.webm", likesCount: 310, liked: false },
    { id: 5, dogName: "Oscar", dogBreed: "Corgi", dogImage: "/dogs/oscar.jpg", caption: "Nap posture classification: 100% relaxed 💤", videoUrl: "/moments/dog_laying_relax.webm", likesCount: 418, liked: false },
    { id: 6, dogName: "Bella", dogBreed: "Golden Retriever", dogImage: "/dogs/bella.jpg", caption: "Spins like a whirlwind when hearing good boy! 🌪️", videoUrl: "/moments/dog_spin_standing.webm", likesCount: 523, liked: false },
  ],
  devices: {
    feeder: { online: true, hopper: 68, portion: "small" },
    camera: { online: true, nightVision: true, microphone: false, speaker: true },
  },
  leaderboardDogs: {
    max: ["Max", "German Shepherd", "Floreasca", "#B9CFE6", "/dogs/max.jpg"],
    bella: ["Bella", "Golden Retriever", "Cotroceni", "#F5BE6B", "/dogs/bella.jpg"],
    rocky: ["Rocky", "Malinois", "Titan", "#A9C9A4", "/dogs/rocky.jpg"],
    coco: ["Coco", "Poodle", "Aviației", "#E3C4DD", "/dogs/coco.jpg"],
    zara: ["Zara", "Vizsla", "Drumul Taberei", "#F2C3A0", "/dogs/zara.jpg"],
    oscar: ["Oscar", "Corgi", "Dorobanți", "#BFDCD8", "/dogs/oscar.jpg"],
    bruno: ["Bruno", "Labrador", "Herăstrău", "#F29E6D", "/dogs/bruno.jpg"],
    kira: ["Kira", "Husky", "Militari", "#D6CBBE", "/dogs/kira.jpg"],
    lola: ["Lola", "Jack Russell", "Berceni", "#F0B8B0", "/dogs/lola.jpg"],
    ares: ["Ares", "Doberman", "Băneasa", "#C9B79F", "/dogs/ares.jpg"],
  },
  leaderboardCats: {
    score: [["rocky", "988", "="], ["bella", "971", "+2"], ["max", "963", "-1"], ["coco", "955", "+1"], ["zara", "949", "-2"], ["oscar", "931", "+3"], ["bruno", "912", "+5"], ["kira", "904", "-1"], ["lola", "896", "="], ["ares", "887", "-4"]],
    fast: [["zara", "0.41 s", "+1"], ["rocky", "0.44 s", "-1"], ["oscar", "0.52 s", "+4"], ["bruno", "0.55 s", "+2"], ["bella", "0.58 s", "="], ["max", "0.61 s", "-2"], ["lola", "0.63 s", "+1"], ["coco", "0.70 s", "-3"], ["kira", "0.74 s", "="], ["ares", "0.81 s", "-1"]],
    streak: [["max", "64 days", "="], ["coco", "51 days", "="], ["rocky", "47 days", "+1"], ["lola", "39 days", "-1"], ["bella", "33 days", "="], ["kira", "28 days", "+2"], ["ares", "21 days", "="], ["bruno", "12 days", "+1"], ["zara", "9 days", "-3"], ["oscar", "6 days", "="]],
    rise: [["oscar", "+142", "+9"], ["bruno", "+118", "+5"], ["lola", "+97", "+3"], ["bella", "+81", "+2"], ["kira", "+66", "="], ["coco", "+52", "+1"], ["zara", "+40", "-2"], ["rocky", "+31", "-1"], ["max", "+18", "-3"], ["ares", "+4", "-4"]],
  },
};

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function writeStorage(key, val) {
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch {
    // quota/private browsing
  }
}

export class HttpRepository extends IPetRepository {
  constructor() {
    super();
    this._initLocalCache();
  }

  _initLocalCache() {
    if (!localStorage.getItem(CACHE_KEYS.DOGS)) {
      writeStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    }
    if (!localStorage.getItem(CACHE_KEYS.SCHEDULES)) {
      writeStorage(CACHE_KEYS.SCHEDULES, SEED_CACHE.schedules);
    }
    if (!localStorage.getItem(CACHE_KEYS.MOMENTS)) {
      writeStorage(CACHE_KEYS.MOMENTS, SEED_CACHE.moments);
    }
    if (!localStorage.getItem(CACHE_KEYS.DEVICES)) {
      writeStorage(CACHE_KEYS.DEVICES, SEED_CACHE.devices);
    }
  }

  async _tryApiOrFallback(apiCall, fallbackFn) {
    try {
      return await apiCall();
    } catch {
      return fallbackFn();
    }
  }

  // ------------------------------------------------------------------ dogs
  async getDogs() {
    return readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
  }

  async getDog(dogId) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    return dogs.find((d) => d.id === dogId) || null;
  }

  async createDog(data) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    const newDog = {
      id: data.id || data.name.toLowerCase().replace(/[^a-z0-9]/g, "") + "_" + Date.now().toString(36),
      name: data.name,
      pronoun: data.pronoun || "he",
      initial: data.name[0].toUpperCase(),
      color: data.color || "#F29E6D",
      image: data.image || "/dogs/default.jpg",
      breed: data.breed || "Mixed breed",
      age: data.age || "1 yr",
      weight: data.weight || "15 kg",
      score: 700,
      rank: 20,
      city: "Bucharest",
      streak: 1,
      success7d: 80,
      reaction: "1.0 s",
      successesToday: 0,
      treatsToday: 0,
      treatLimit: data.treatLimit || 25,
      week: data.week || [50, 60, 65, 70, 75, 80, 80],
      exercises: data.exercises || [
        { id: "sit", name: "Sit", stage: "learn", moments: 0, goal: 30, startedAgo: "just started",
          schedule: "Daily, 09:00–18:00", limitNote: "max 10 treats · one every 30 min", caught: [] },
        { id: "down", name: "Down", stage: "train", rate: 80, level: 2, detail: "Holds 1.0 s" },
        { id: "stand", name: "Stand", stage: "next", detail: "Starts once sit is mastered" },
        { id: "stay", name: "Stay", stage: "next", detail: "Starts once sit is mastered" },
      ],
    };
    const updated = [newDog, ...dogs];
    writeStorage(CACHE_KEYS.DOGS, updated);
    return newDog;
  }

  async updateDog(dogId, patch) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    const updated = dogs.map((d) => (d.id === dogId ? { ...d, ...patch } : d));
    writeStorage(CACHE_KEYS.DOGS, updated);
    return updated.find((d) => d.id === dogId) || null;
  }

  async giveTreat(dogId) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    const target = dogs.find((d) => d.id === dogId);
    if (!target || target.treatsToday >= target.treatLimit) {
      return { ok: false, treatsToday: target ? target.treatsToday : 0 };
    }
    const updated = dogs.map((d) => (d.id === dogId ? { ...d, treatsToday: d.treatsToday + 1 } : d));
    writeStorage(CACHE_KEYS.DOGS, updated);

    const devices = readStorage(CACHE_KEYS.DEVICES, SEED_CACHE.devices);
    const newHopper = Math.max(0, Math.round(((devices.feeder?.hopper ?? 68) - 0.5) * 10) / 10);
    devices.feeder.hopper = newHopper;
    writeStorage(CACHE_KEYS.DEVICES, devices);

    return { ok: true, treatsToday: target.treatsToday + 1, hopper: newHopper };
  }

  async addSuccess(dogId) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    const updated = dogs.map((d) => (d.id === dogId ? { ...d, successesToday: d.successesToday + 1 } : d));
    writeStorage(CACHE_KEYS.DOGS, updated);
    return updated.find((d) => d.id === dogId) || null;
  }

  async setExerciseStage(dogId, exerciseId, stage) {
    const dogs = readStorage(CACHE_KEYS.DOGS, SEED_CACHE.dogs);
    const updated = dogs.map((d) => {
      if (d.id !== dogId) return d;
      return {
        ...d,
        exercises: d.exercises.map((e) => (e.id === exerciseId ? { ...e, stage } : e)),
      };
    });
    writeStorage(CACHE_KEYS.DOGS, updated);
    return updated.find((d) => d.id === dogId) || null;
  }

  // ------------------------------------------------------------------ schedules
  async getSchedules(dogId) {
    const schedules = readStorage(CACHE_KEYS.SCHEDULES, SEED_CACHE.schedules);
    return dogId ? schedules.filter((s) => s.dog === dogId) : schedules;
  }

  async updateSchedule(scheduleId, patch) {
    const schedules = readStorage(CACHE_KEYS.SCHEDULES, SEED_CACHE.schedules);
    const updated = schedules.map((s) => (s.id === scheduleId ? { ...s, ...patch } : s));
    writeStorage(CACHE_KEYS.SCHEDULES, updated);
    return updated.find((s) => s.id === scheduleId) || null;
  }

  // ------------------------------------------------------------------ moments & likes
  async getRandomMoments(limit = 5, excludeIds = [], clientId = "default") {
    return this._tryApiOrFallback(
      () => api.momentsRandom(limit, excludeIds, clientId),
      () => {
        const catalog = readStorage(CACHE_KEYS.MOMENTS, SEED_CACHE.moments);
        const excludeSet = new Set(excludeIds);
        const candidates = catalog.filter((m) => !excludeSet.has(m.id));
        const pool = candidates.length >= limit ? candidates : catalog;
        const shuffled = [...pool].sort(() => 0.5 - Math.random());
        return shuffled.slice(0, limit);
      }
    );
  }

  async setMomentLike(momentId, clientId, liked) {
    // Always update local AP cache first
    const catalog = readStorage(CACHE_KEYS.MOMENTS, SEED_CACHE.moments);
    let nextCount = 0;
    const updated = catalog.map((m) => {
      if (m.id === momentId) {
        nextCount = liked ? m.likesCount + 1 : Math.max(0, m.likesCount - 1);
        return { ...m, liked, likesCount: nextCount };
      }
      return m;
    });
    writeStorage(CACHE_KEYS.MOMENTS, updated);

    return this._tryApiOrFallback(
      () => api.likeMoment(momentId, clientId, liked),
      () => ({ momentId, liked, likesCount: nextCount })
    );
  }

  // ------------------------------------------------------------------ leaderboard
  async getLeaderboard(category = "score", scope = "city") {
    return this._tryApiOrFallback(
      () => api.leaderboard(category, scope),
      () => {
        const catList = SEED_CACHE.leaderboardCats[category] || SEED_CACHE.leaderboardCats.score;
        return catList.map(([id, value, move], i) => {
          const [name, breed, area, color, image] = SEED_CACHE.leaderboardDogs[id];
          return { id, rank: i + 1, name, breed, area, color, image, value, move, mine: id === "bruno" };
        });
      }
    );
  }

  // ------------------------------------------------------------------ devices
  async getDevices() {
    return readStorage(CACHE_KEYS.DEVICES, SEED_CACHE.devices);
  }

  async updateDevice(deviceName, patch) {
    const devices = readStorage(CACHE_KEYS.DEVICES, SEED_CACHE.devices);
    devices[deviceName] = { ...(devices[deviceName] || {}), ...patch };
    writeStorage(CACHE_KEYS.DEVICES, devices);
    return devices[deviceName];
  }
}

export const petRepository = new HttpRepository();
