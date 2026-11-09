// App-wide state (dogs, schedules, device settings, toasts).
//
// On start the app looks for the backend (python -m server):
//   source "api"   data comes from the server and every change is sent to it
//   source "mock"  no server found: the in-memory demo data from data/mock.js (offline demo)
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";
import { DOGS, SCHEDULES, WEEK_ALL, WEEK_DAYS } from "./data/mock.js";
import { toDog, toSchedule, weekLabels, weekValues } from "./data/fromApi.js";

const StoreContext = createContext(null);
const REFRESH_MS = 5000;

export function StoreProvider({ children }) {
  const [source, setSource] = useState("loading");
  const [health, setHealth] = useState(null);
  const [dogs, setDogs] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [week, setWeek] = useState({ values: WEEK_ALL, labels: WEEK_DAYS });
  const [feeder, setFeeder] = useState({ online: true, hopper: 68, portion: "small" });
  const [camera, setCamera] = useState({ online: true, nightVision: true, microphone: false, speaker: true });
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current);
    setToast(text);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
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
        if (cancelled) return;
        setHealth(h);
        setFeeder((f) => ({ ...f, online: true }));
        setCamera((c) => ({ ...c, online: h.camera }));
        setSource("api");
      } catch {
        if (cancelled) return;
        setDogs(DOGS);
        setSchedules(SCHEDULES);
        setSource("mock");
      }
    })();
    return () => { cancelled = true; };
  }, [refresh]);

  useEffect(() => {
    if (source !== "api") return undefined;
    const id = setInterval(() => refresh().catch(() => {}), REFRESH_MS);
    return () => clearInterval(id);
  }, [source, refresh]);

  // ---------------------------------------------------------------- local helpers (mock mode)
  const updateDog = useCallback((id, fn) => {
    setDogs((ds) => ds.map((d) => (d.id === id ? fn(d) : d)));
  }, []);

  const dogsRef = useRef(dogs);
  dogsRef.current = dogs;

  /** Mock mode: gives a treat to a dog if under its daily limit. Returns true if dispensed. */
  const giveTreat = useCallback((id) => {
    const dog = dogsRef.current.find((d) => d.id === id);
    if (!dog || dog.treatsToday >= dog.treatLimit) return false;
    dogsRef.current = dogsRef.current.map((d) => (d.id === id ? { ...d, treatsToday: d.treatsToday + 1 } : d));
    setDogs(dogsRef.current);
    setFeeder((f) => ({ ...f, hopper: Math.max(0, Math.round((f.hopper - 0.5) * 10) / 10) }));
    return true;
  }, []);

  const addSuccess = useCallback((id) => {
    updateDog(id, (d) => ({ ...d, successesToday: d.successesToday + 1 }));
  }, [updateDog]);

  // ---------------------------------------------------------------- actions (both modes)
  /** Optimistic local change, then the server; on error the server's data comes back. */
  const sync = useCallback(async (call) => {
    if (source !== "api") return;
    try {
      await call();
    } catch (err) {
      showToast(err.message || "The server didn't accept that");
    }
    refresh().catch(() => {});
  }, [source, refresh, showToast]);

  const setExerciseStage = useCallback((dogId, exId, stage) => {
    updateDog(dogId, (d) => ({ ...d, exercises: d.exercises.map((e) => (e.id === exId ? { ...e, stage } : e)) }));
    const dog = dogsRef.current.find((d) => d.id === dogId);
    sync(() => api.setStage(dog.apiId, exId, stage));
  }, [updateDog, sync]);

  const updateSchedule = useCallback((id, patch) => {
    setSchedules((ss) => ss.map((s) => (s.id === id ? { ...s, ...patch } : s)));
    const body = {};
    if ("on" in patch) body.enabled = patch.on;
    if ("max" in patch) body.max_treats = patch.max;
    sync(() => api.updateSchedule(id, body));
  }, [sync]);

  /** "Dispense a test treat" in Settings > Feeder. */
  const testTreat = useCallback(async () => {
    if (source !== "api") return true;
    try {
      return (await api.testTreat()).ok;
    } catch {
      return false;
    }
  }, [source]);

  const value = useMemo(() => ({
    source, health, dogs, schedules, week, feeder, camera, toast,
    getDog: (id) => dogs.find((d) => d.id === String(id)),
    showToast, refresh, giveTreat, addSuccess, setExerciseStage, updateSchedule, testTreat, setFeeder, setCamera,
  }), [source, health, dogs, schedules, week, feeder, camera, toast, showToast, refresh, giveTreat, addSuccess,
    setExerciseStage, updateSchedule, testTreat]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  return useContext(StoreContext);
}
