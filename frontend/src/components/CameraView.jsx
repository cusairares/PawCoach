// Live camera view. With a real camera (backend in camera mode) it shows the server's video
// stream (`streamSrc`, MJPEG). Otherwise it shows a dog photo matching the detected pose.
// No box or pose label on top: just the dog.

const POSE_IMAGES = {
  sitting: "/dogs/pose_sitting.jpg",
  standing: "/dogs/pose_standing.jpg",
  lying: "/dogs/pose_lying.jpg",
};

export default function CameraView({ pose, poseLabel, streamSrc = null, children }) {
  const imgSrc = (pose && POSE_IMAGES[pose]) || "/dogs/living_room_dog.jpg";

  return (
    <div className="cam" role="img" aria-label={`Live camera: dog is ${poseLabel?.toLowerCase() ?? "not in view"}`}>
      {streamSrc ? (
        <img className="cam-stream" src={streamSrc} alt="" />
      ) : (
        <>
          <img
            src={imgSrc}
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
