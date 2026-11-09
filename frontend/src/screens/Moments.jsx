import { useEffect, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";
import { useStore } from "../store.jsx";

function MomentCard({ moment, onLike }) {
  const videoRef = useRef(null);
  const cardRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showHeartBurst, setShowHeartBurst] = useState(false);
  const lastTapRef = useRef(0);

  // Play when visible, pause when scrolled away
  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const video = videoRef.current;
          if (!video) return;
          if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
            video.muted = true;
            video.play()
              .then(() => setIsPlaying(true))
              .catch(() => setIsPlaying(false));
          } else {
            video.pause();
            setIsPlaying(false);
          }
        });
      },
      { threshold: [0.1, 0.5, 0.8] }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.muted = true;
      video.play()
        .then(() => setIsPlaying(true))
        .catch((err) => console.warn("Video play blocked:", err));
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleCardClick = () => {
    const now = Date.now();
    // Double-tap detection
    if (now - lastTapRef.current < 320) {
      if (!moment.liked) {
        onLike(moment.id);
      }
      setShowHeartBurst(true);
      setTimeout(() => setShowHeartBurst(false), 900);
      lastTapRef.current = 0;
    } else {
      lastTapRef.current = now;
      togglePlay();
    }
  };

  return (
    <article ref={cardRef} className="moment-card" onClick={handleCardClick}>
      <video
        ref={videoRef}
        src={moment.videoUrl}
        poster={moment.dogImage}
        className="moment-video"
        loop
        muted
        autoPlay
        playsInline
        preload="auto"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />

      <div className="moment-scrim" />

      {/* Double tap heart animation */}
      {showHeartBurst && (
        <div className="heart-burst" aria-hidden="true">
          <Icon name="heartFilled" size={96} />
        </div>
      )}

      {/* Play/Pause indicator overlay */}
      {!isPlaying && (
        <div className="play-overlay" aria-hidden="true">
          <span className="play-icon-circle">▶</span>
        </div>
      )}

      {/* Bottom overlay: Pet details & caption */}
      <div className="moment-info">
        <div className="moment-dog-row">
          <Avatar dog={{ name: moment.dogName, image: moment.dogImage }} size={44} ring="#FFFFFF" />
          <div className="stack-2">
            <strong className="moment-dog-name">{moment.dogName}</strong>
            <span className="moment-dog-breed">{moment.dogBreed}</span>
          </div>
        </div>
        <p className="moment-caption">{moment.caption}</p>
      </div>

      {/* Right interaction rail: ONLY the like button */}
      <aside className="moment-actions" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className={`moment-like-btn ${moment.liked ? "is-liked" : ""}`}
          aria-label={moment.liked ? `Unlike moment (${moment.likesCount} likes)` : `Like moment (${moment.likesCount} likes)`}
          aria-pressed={moment.liked}
          onClick={() => {
            onLike(moment.id);
            if (!moment.liked) {
              setShowHeartBurst(true);
              setTimeout(() => setShowHeartBurst(false), 800);
            }
          }}
        >
          <span className="like-icon-wrap">
            <Icon name={moment.liked ? "heartFilled" : "heart"} size={32} strokeWidth={2.4} />
          </span>
          <span className="like-count">{moment.likesCount}</span>
        </button>
      </aside>
    </article>
  );
}

export default function Moments() {
  const { moments, toggleLikeMoment, loadMoreRandomMoments, apStatus } = useStore();
  const feedRef = useRef(null);

  // Infinite random video scrolling detection
  const handleScroll = (e) => {
    const el = e.currentTarget;
    if (el.scrollHeight - (el.scrollTop + el.clientHeight) < 400) {
      loadMoreRandomMoments(3);
    }
  };

  return (
    <div className="moments-feed-container">
      {/* Top status bar with AP partition status indicator */}
      <header className="moments-top-bar">
        <h1>Moments</h1>
        <div className="ap-badge" title="CAP theorem: Available & Partition-Tolerant write-behind engine">
          <span className={`status-dot ${apStatus === "synced" ? "is-synced" : "is-queued"}`} />
          <span>{apStatus === "synced" ? "AP Live" : "Offline · Queued"}</span>
        </div>
      </header>

      {/* Snap-scroll feed container */}
      <main
        ref={feedRef}
        className="moments-snap-feed"
        onScroll={handleScroll}
        aria-label="Funny pet moments feed"
      >
        {moments.map((m, idx) => (
          <MomentCard
            key={m.instanceKey || `${m.id}_${idx}`}
            moment={m}
            onLike={toggleLikeMoment}
          />
        ))}

        <div className="moments-loading-tail">
          <span className="muted small">Loading more random moments…</span>
        </div>
      </main>
    </div>
  );
}
