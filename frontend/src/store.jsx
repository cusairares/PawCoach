// App-wide state for the prototype (dogs, schedules, device settings, toasts).
// In the real app this state lives on the backend; here it is in memory only.
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { DOGS, SCHEDULES } from "./data/mock.js";

const StoreContext = createContext(null);

export function StoreProvider({ children }) {
  const [dogs, setDogs] = useState(DOGS);
  const [schedules, setSchedules] = useState(SCHEDULES);
  const [feeder, setFeeder] = useState({ online: true, hopper: 68, portion: "small" });
  const [camera, setCamera] = useState({ online: true, nightVision: true, microphone: false, speaker: true });
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current);
    setToast(text);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }, []);

  const updateDog = useCallback((id, fn) => {
    setDogs((ds) => ds.map((d) => (d.id === id ? fn(d) : d)));
  }, []);

  const dogsRef = useRef(dogs);
  dogsRef.current = dogs;

  /** Gives a treat to a dog if under its daily limit. Returns true if dispensed. */
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

  const setExerciseStage = useCallback((dogId, exId, stage) => {
    updateDog(dogId, (d) => ({ ...d, exercises: d.exercises.map((e) => (e.id === exId ? { ...e, stage } : e)) }));
  }, [updateDog]);

  const updateSchedule = useCallback((id, patch) => {
    setSchedules((ss) => ss.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }, []);

  const value = useMemo(() => ({
    dogs, schedules, feeder, camera, toast,
    getDog: (id) => dogs.find((d) => d.id === id),
    showToast, giveTreat, addSuccess, setExerciseStage, updateSchedule, setFeeder, setCamera,
  }), [dogs, schedules, feeder, camera, toast, showToast, giveTreat, addSuccess, setExerciseStage, updateSchedule]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  return useContext(StoreContext);
}
