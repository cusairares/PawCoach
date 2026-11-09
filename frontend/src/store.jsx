// App-wide state consuming FastAPI (when server is running) and IPetRepository (HttpRepository)
// for Moments, Leaderboard, and offline AP resilience.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import { WEEK_ALL, WEEK_DAYS } from "./data/mock.js";
import { toDog, toSchedule, weekLabels, weekValues } from "./data/fromApi.js";
import { petRepository } from "./repositories/HttpRepository.js";

const StoreContext = createContext(null);
const REFRESH_MS = 5000;

export function StoreProvider({ children, repository = petRepository }) {
  const [source, setSource] = useState("loading");
  const [health, setHealth] = useState(null);
  const [dogs, setDogs] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [week, setWeek] = useState({ values: WEEK_ALL, labels: WEEK_DAYS });
  const [feeder, setFeeder] = useState({ online: true, hopper: 68, portion: "small" });
  const [camera, setCamera] = useState({ online: true, nightVision: true, microphone: false, speaker: true });
  const [toast, setToast] = useState(null);
  const [error, setError] = useState(null);
  const [feedMoments, setFeedMoments] = useState([]);
  const [apStatus, setApStatus] = useState("synced");
  const toastTimer = useRef(null);

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current);
    setToast(text);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  }, []);

  const showError = useCallback((message) => {
    setError(String(message || "Something went wrong"));
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // ---------------------------------------------------------------- loading
  const refresh = useCallback(async () => {
    const [apiDogs, apiSchedules, daily] = await Promise.all([api.dogs(), api.schedules(), api.daily(7)]);
    setDogs(apiDogs.map((d) => toDog(d, apiSchedules)));
    setSchedules(apiSchedules.map((s) => toSchedule(s, apiDogs)));
    setWeek({ values: weekValues(daily), labels: weekLabels(daily) });
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await api.health();
        await refresh();
        const initialMoments = await repository.getRandomMoments(6);
        if (cancelled) return;
        setHealth(h);
        setFeeder((f) => ({ ...f, online: true }));
        setCamera((c) => ({ ...c, online: h.camera }));
        setFeedMoments(initialMoments);
        setApStatus("synced");
        setSource("api");
      } catch {
        if (cancelled) return;
        const [dogsList, schedulesList, devicesData, initialMoments] = await Promise.all([
          repository.getDogs(),
          repository.getSchedules(),
          repository.getDevices(),
          repository.getRandomMoments(6),
        ]);
        if (cancelled) return;
        setDogs(dogsList);
        setSchedules(schedulesList);
        if (devicesData?.feeder) setFeeder(devicesData.feeder);
        if (devicesData?.camera) setCamera(devicesData.camera);
        setFeedMoments(initialMoments);
        setApStatus("offline");
        setSource("mock");
      }
    })();
    return () => { cancelled = true; };
  }, [refresh, repository]);

  useEffect(() => {
    if (source !== "api") return undefined;
    const id = setInterval(() => refresh().catch(() => {}), REFRESH_MS);
    return () => clearInterval(id);
  }, [source, refresh]);

  // ---------------------------------------------------------------- local helpers & actions
  const updateDogLocal = useCallback((id, fn) => {
    setDogs((ds) => ds.map((d) => (d.id === id ? fn(d) : d)));
  }, []);

  const dogsRef = useRef(dogs);
  dogsRef.current = dogs;

  /** Optimistic local change, then the server; on error the server's error dialog is shown and data comes back. */
  const sync = useCallback(async (call) => {
    if (source !== "api") return;
    try {
      await call();
    } catch (err) {
      showError(err.message || "The server didn't accept that");
    }
    refresh().catch(() => {});
  }, [source, refresh, showError]);

  const addDog = useCallback(async (data) => {
    if (source === "api") {
      try {
        const weightNum = parseFloat(String(data.weight || "").replace(/[^0-9.]/g, ""));
        const created = await api.addDog({
          name: data.name.trim(),
          breed: data.breed || "Mixed breed",
          weight_kg: Number.isFinite(weightNum) && weightNum > 0 ? weightNum : null,
          age_text: data.age || "1 yr",
          image_url: data.image || "/dogs/default.jpg",
          pronoun: data.pronoun || "he",
        });
        await refresh();
        showToast(`${created.name} added to your family!`);
        return created;
      } catch (err) {
        showError(err.message || "Couldn't add pet");
        return null;
      }
    }
    const created = await repository.createDog(data);
    setDogs((prev) => [created, ...prev]);
    showToast(`${created.name} added to your family!`);
    return created;
  }, [source, refresh, repository, showToast, showError]);

  /** Mock mode: gives a treat to a dog if under its daily limit. Returns true if dispensed. */
  const giveTreat = useCallback((id) => {
    const dog = dogsRef.current.find((d) => d.id === id);
    if (!dog || dog.treatsToday >= dog.treatLimit) return false;
    dogsRef.current = dogsRef.current.map((d) => (d.id === id ? { ...d, treatsToday: d.treatsToday + 1 } : d));
    setDogs(dogsRef.current);
    setFeeder((f) => ({ ...f, hopper: Math.max(0, Math.round((f.hopper - 0.5) * 10) / 10) }));
    repository.giveTreat(id).catch(() => {});
    return true;
  }, [repository]);

  const addSuccess = useCallback((id) => {
    updateDogLocal(id, (d) => ({ ...d, successesToday: d.successesToday + 1 }));
    repository.addSuccess(id).catch(() => {});
  }, [updateDogLocal, repository]);

  const setExerciseStage = useCallback((dogId, exId, stage) => {
    updateDogLocal(dogId, (d) => ({ ...d, exercises: d.exercises.map((e) => (e.id === exId ? { ...e, stage } : e)) }));
    repository.setExerciseStage(dogId, exId, stage).catch(() => {});
    const dog = dogsRef.current.find((d) => d.id === dogId);
    if (dog?.apiId != null) {
      sync(() => api.setStage(dog.apiId, exId, stage));
    }
  }, [updateDogLocal, repository, sync]);

  const updateSchedule = useCallback((id, patch) => {
    setSchedules((ss) => ss.map((s) => (s.id === id ? { ...s, ...patch } : s)));
    repository.updateSchedule(id, patch).catch(() => {});
    const body = {};
    if ("on" in patch) body.enabled = patch.on;
    if ("max" in patch) body.max_treats = patch.max;
    sync(() => api.updateSchedule(id, body));
  }, [repository, sync]);

  /** "Dispense a test treat" in Settings > Feeder. */
  const testTreat = useCallback(async () => {
    if (source !== "api") return true;
    try {
      return (await api.testTreat()).ok;
    } catch (err) {
      showError(err.message || "The feeder didn't respond");
      return false;
    }
  }, [source, showError]);

  const toggleLikeMoment = useCallback(async (momentId) => {
    let nextLiked = false;
    setFeedMoments((prev) =>
      prev.map((m) => {
        if (m.id === momentId) {
          nextLiked = !m.liked;
          const likesCount = nextLiked ? m.likesCount + 1 : Math.max(0, m.likesCount - 1);
          return { ...m, liked: nextLiked, likesCount };
        }
        return m;
      })
    );
    await repository.setMomentLike(momentId, "user_me", nextLiked);
  }, [repository]);

  const loadMoreRandomMoments = useCallback(async (count = 3) => {
    const lastIds = feedMoments.slice(-count).map((m) => m.id);
    const newItems = await repository.getRandomMoments(count, lastIds);
    setFeedMoments((prev) => [
      ...prev,
      ...newItems.map((item, idx) => ({
        ...item,
        instanceKey: `${item.id}_${Date.now()}_${idx}`,
      })),
    ]);
  }, [feedMoments, repository]);

  const value = useMemo(() => ({
    repository,
    source, health, dogs, schedules, week, feeder, camera, toast, error,
    moments: feedMoments, apStatus,
    getDog: (id) => dogs.find((d) => d.id === String(id)),
    addDog, showToast, showError, clearError, refresh, giveTreat, addSuccess,
    setExerciseStage, updateSchedule, testTreat,
    setFeeder, setCamera,
    toggleLikeMoment, loadMoreRandomMoments,
  }), [
    repository, source, health, dogs, schedules, week, feeder, camera, toast, error,
    feedMoments, apStatus, addDog, showToast, showError, clearError, refresh,
    giveTreat, addSuccess, setExerciseStage, updateSchedule, testTreat,
    toggleLikeMoment, loadMoreRandomMoments,
  ]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  return useContext(StoreContext);
}
