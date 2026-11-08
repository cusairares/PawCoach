// Tiny hash router (no dependency). Routes look like  #/dogs/bruno/exercises/down
import { useEffect, useState } from "react";

const DEFAULT = "/home";

function current() {
  const h = window.location.hash.replace(/^#/, "");
  return h || DEFAULT;
}

export function useRoute() {
  const [path, setPath] = useState(current);
  useEffect(() => {
    const onChange = () => {
      setPath(current());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return path;
}

/** Matches "/dogs/:id" against "/dogs/bruno" -> { id: "bruno" } (or null). */
export function match(pattern, path) {
  const p = pattern.split("/").filter(Boolean);
  const s = path.split("/").filter(Boolean);
  if (p.length !== s.length) return null;
  const params = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(":")) params[p[i].slice(1)] = decodeURIComponent(s[i]);
    else if (p[i] !== s[i]) return null;
  }
  return params;
}

export function Link({ to, children, ...rest }) {
  return (
    <a href={`#${to}`} {...rest}>
      {children}
    </a>
  );
}
