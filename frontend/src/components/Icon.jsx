// Inline stroke icons (no icon library needed).
const PATHS = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  moments: <><rect x="4" y="3" width="16" height="18" rx="4" /><path d="M10 9v6l5-3z" /></>,
  live: <><rect x="2.5" y="6" width="13" height="12" rx="2.5" /><path d="m15.5 10 6-3.5v11l-6-3.5" /></>,
  trophy: <><path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z" /><path d="M7 6H4v1.5A3.5 3.5 0 0 0 7.5 11M17 6h3v1.5a3.5 3.5 0 0 1-3.5 3.5" /></>,
  settings: <><path d="M4 7h9M17 7h3M4 17h3M11 17h9" /><circle cx="15" cy="7" r="2" /><circle cx="9" cy="17" r="2" /></>,
  chevronRight: <path d="m9 6 6 6-6 6" />,
  chevronLeft: <path d="m15 6-6 6 6 6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="m5 12 5 5 9-10" />,
  mic: <><path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></>,
  calendar: <><rect x="4" y="6" width="16" height="14" rx="2" /><path d="M4 10h16M8 3v4M16 3v4" /></>,
  feeder: <><path d="M7 3h10l-1.5 7h-7z" /><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M10 15h4" /></>,
  camera: <><rect x="2.5" y="6" width="13" height="12" rx="2" /><path d="m15.5 10 6-3.5v11l-6-3.5" /></>,
  bell: <path d="M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 21h4" />,
  share: <path d="M14 5l7 7-7 7v-4c-5 0-8 1.5-10 5 0-6 3-10 10-11z" />,
  lock: <><rect x="6" y="11" width="12" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7M12 17h.01" /></>,
  arrowRight: <path d="M5 12h14m-5-5 5 5-5 5" />,
  heart: <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />,
  heartFilled: <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" fill="currentColor" />,
  refresh: <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />,
  x: <path d="M18 6 6 18M6 6l12 12" />,
};

export default function Icon({ name, size = 22, strokeWidth = 1.9, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {PATHS[name]}
    </svg>
  );
}
