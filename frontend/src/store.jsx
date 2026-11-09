// App-wide state consuming IPetRepository (implemented by HttpRepository).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { petRepository } from "./repositories/HttpRepository.js";

const StoreContext = createContext(null);

export function StoreProvider({ children, repository = petRepository }) {
  const [dogs, setDogs] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [feeder, setFeeder] = useState({ online: true, hopper: 68, portion: "small" });
  const [camera, setCamera] = useState({ online: true, nightVision: true, microphone: false, speaker: true });
  const [toast, setToast] = useState(null);
  const [feedMoments, setFeedMoments] = useState([]);
  const [apStatus, setApStatus] = useState("synced");
  const toastTimer = useRef(null);

  // Load domain state from repository on startup
  useEffect(() => {
    let mounted = true;
    async function loadData() {
      try {
        const [dogsList, schedulesList, devicesData, initialMoments] = await Promise.all([
          repository.getDogs(),
          repository.getSchedules(),
          repository.getDevices(),
          repository.getRandomMoments(6),
        ]);
        if (!mounted) return;
        setDogs(dogsList);
        setSchedules(schedulesList);
        if (devicesData?.feeder) setFeeder(devicesData.feeder);
        if (devicesData?.camera) setCamera(devicesData.camera);
        setFeedMoments(initialMoments);
      } catch (err) {
        console.warn("Error loading data from repository:", err);
      }
    }
    loadData();
    return () => { mounted = false; };
  }, [repository]);

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current);
    setToast(text);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  }, []);

  const addDog = useCallback(async (data) => {
    const created = await repository.createDog(data);
    setDogs((prev) => [created, ...prev]);
    showToast(`${created.name} added to your family!`);
    return created;
  }, [repository, showToast]);

  const giveTreat = useCallback(async (dogId) => {
    const res = await repository.giveTreat(dogId);
    if (!res.ok) return false;
    setDogs((prev) =>
      prev.map((d) => (d.id === dogId ? { ...d, treatsToday: res.treatsToday } : d))
    );
    if (res.hopper !== undefined) {
      setFeeder((f) => ({ ...f, hopper: res.hopper }));
    }
    return true;
  }, [repository]);

  const addSuccess = useCallback(async (dogId) => {
    const updated = await repository.addSuccess(dogId);
    if (updated) {
      setDogs((prev) => prev.map((d) => (d.id === dogId ? updated : d)));
    }
  }, [repository]);

  const setExerciseStage = useCallback(async (dogId, exId, stage) => {
    const updated = await repository.setExerciseStage(dogId, exId, stage);
    if (updated) {
      setDogs((prev) => prev.map((d) => (d.id === dogId ? updated : d)));
    }
  }, [repository]);

  const updateSchedule = useCallback(async (id, patch) => {
    const updated = await repository.updateSchedule(id, patch);
    if (updated) {
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
    }
  }, [repository]);

  const updateFeeder = useCallback(async (patch) => {
    const nextFeeder = { ...feeder, ...patch };
    setFeeder(nextFeeder);
    await repository.updateDevice("feeder", patch);
  }, [feeder, repository]);

  const updateCamera = useCallback(async (patch) => {
    const nextCamera = { ...camera, ...patch };
    setCamera(nextCamera);
    await repository.updateDevice("camera", patch);
  }, [camera, repository]);

  const toggleLikeMoment = useCallback(async (momentId) => {
    // Optimistic UI update
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
    // Persist via repository
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
    dogs, schedules, feeder, camera, toast,
    moments: feedMoments, apStatus,
    getDog: (id) => dogs.find((d) => d.id === id),
    addDog, showToast, giveTreat, addSuccess, setExerciseStage,
    updateSchedule, setFeeder: updateFeeder, setCamera: updateCamera,
    toggleLikeMoment, loadMoreRandomMoments,
  }), [
    repository, dogs, schedules, feeder, camera, toast, feedMoments, apStatus,
    addDog, showToast, giveTreat, addSuccess, setExerciseStage, updateSchedule,
    updateFeeder, updateCamera, toggleLikeMoment, loadMoreRandomMoments,
  ]);

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  return useContext(StoreContext);
}
