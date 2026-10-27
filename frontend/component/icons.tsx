const paths: Record<string, string> = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  car: "m5 8 2-5h10l2 5 M3 9h18v9H3z M6 18v3 M18 18v3 M6 12h2 M16 12h2",
  camera: "M3 6h12v13H3z m12 5 6-4v12l-6-4",
  clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z",
  arrow: "M5 12h14 m-5-5 5 5-5 5",
  refresh: "M20 8a9 9 0 1 0 1 8 M20 3v6h-6",
  download: "M12 3v12 m-5-5 5 5 5-5 M4 17v4h16v-4",
  upload: "M12 16V4 m-5 5 5-5 5 5 M4 17v4h16v-4",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 m5 12 6 6",
  check: "m5 12 4 4L19 6",
  bell: "M5 17h14l-2-4V8a5 5 0 0 0-10 0v5z M10 21h4",
  chevron: "m9 5 7 7-7 7",
  info: "M12 11v6 M12 7v1 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  close: "m6 6 12 12 M6 18 18 6",
  signal: "M3 20v-3 M9 20v-7 M15 20V9 M21 20V4",
  exit: "M10 4H4v16h6 M10 12h11 m-5-5 5 5-5 5",
};
export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.info} />
    </svg>
  );
}
export function Car({ color = "#5e786f" }: { color?: string }) {
  return (
    <svg className="car-art" viewBox="0 0 48 90" fill="none" aria-hidden="true">
      <path
        d="M7 19v13m34-13v13M7 61v13m34-13v13"
        stroke="#32443d"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <rect x="8" y="3" width="32" height="83" rx="11" fill={color} />
      <path
        d="m14 24 3-10h14l3 10v34l-3 15H17l-3-15z"
        fill="#fff"
        fillOpacity=".1"
        stroke="#fff"
        strokeOpacity=".25"
      />
      <path d="M14 26h20l-3 13H17z M14 61h20l-3-12H17z" fill="#253c36" />
      <path
        d="M11 12h6 M31 12h6"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
        opacity=".8"
      />
      <path
        d="M12 79h5 M31 79h5"
        stroke="#eec5b8"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}
