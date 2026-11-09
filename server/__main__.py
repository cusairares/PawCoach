"""Start the API:  python -m server  [options]

    python -m server                      simulated dog + demo dogs (no camera needed)
    python -m server --fresh              same, but with a new empty database every start
    python -m server --mode camera        real camera + models (webcam 0)
    python -m server --mode camera --camera rtsp://...  --feeder COM3

Then open http://localhost:8000/docs for the API, and start the app (frontend/start.bat).
"""
import argparse
import logging
import os
import tempfile

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m server", description="PawCoach API server")
    ap.add_argument("--mode", choices=["mock", "camera"], default="mock",
                    help="mock = simulated dog (default), camera = real camera + models")
    ap.add_argument("--camera", default="0", help="camera index, video file or rtsp:// URL (camera mode)")
    ap.add_argument("--feeder", default=None, help="serial port of the ESP32 feeder, e.g. COM3 (default: none)")
    ap.add_argument("--host", default="0.0.0.0", help="0.0.0.0 = reachable from phones on the same Wi-Fi")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-demo", action="store_true", help="don't create the demo dogs and schedules")
    ap.add_argument("--fresh", action="store_true", help="use a new temporary database (nothing is kept)")
    ap.add_argument("--data", default=None, help="data folder (default: data/app/server)")
    args = ap.parse_args()

    os.environ["PAWCOACH_MODE"] = args.mode
    os.environ["CAMERA_SOURCE"] = args.camera
    os.environ["PAWCOACH_DEMO"] = "0" if args.no_demo else "1"
    if args.feeder:
        os.environ["FEEDER_PORT"] = args.feeder
    if args.fresh:
        os.environ["PAWCOACH_DATA"] = tempfile.mkdtemp(prefix="pawcoach-")
    elif args.data:
        os.environ["PAWCOACH_DATA"] = args.data

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("server.main:create_app", factory=True, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
