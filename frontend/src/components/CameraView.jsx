import React from "react";

// Live camera view.
// In camera mode or with streamSrc, it streams the MJPEG feed.
// Live passes the server's stream (/api/video): the frames the posture classifier reads.
// Without a stream it falls back to the annotated demo video.

export default function CameraView({
  pose,
  poseLabel,
  streamSrc = null,
  videoSrc = "/moments/video_demo_annotated.mp4",
  children,
}) {
  return (
    <div className="cam" role="img" aria-label={`Live camera: dog is ${poseLabel?.toLowerCase() ?? "not in view"}`}>
      {streamSrc ? (
        <img className="cam-stream" src={streamSrc} alt="Live stream" />
      ) : videoSrc ? (
        <video
          className="cam-stream"
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
          style={{ objectFit: "cover", width: "100%", height: "100%" }}
        />
      ) : (
        <>
          <img
            src={(pose && `/dogs/pose_${pose}.jpg`) || "/dogs/living_room_dog.jpg"}
            alt={pose ? `Dog ${pose}` : "Camera view"}
            className="cam-img-feed"
            onError={(e) => { e.currentTarget.src = "/dogs/living_room_dog.jpg"; }}
          />
          <div className="cam-overlay-shade" />
        </>
      )}

      <span className="cam-chip cam-chip--live"><span className="rec-dot" />LIVE</span>
      {children}
    </div>
  );
}
