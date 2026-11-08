import { BackLink } from "../components/ui.jsx";

export default function NotFound() {
  return (
    <div className="screen">
      <BackLink to="/home" label="Home" />
      <h1>Not found</h1>
      <p className="muted">This page doesn't exist.</p>
    </div>
  );
}
