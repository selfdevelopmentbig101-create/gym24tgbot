/* Icons for the Profile tab (24 px, stroke = currentColor). */
const base = { width: 24, height: 24, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
               strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const Person = () => (
  <svg {...base}><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></svg>
);
export const Pencil = () => (
  <svg {...base}><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M14 6l4 4" /></svg>
);
export const Globe = () => (
  <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18" /></svg>
);
export const Bell = () => (
  <svg {...base}><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z" /><path d="M10 21h4" /></svg>
);
export const Heart = () => (
  <svg {...base}><path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" /></svg>
);
export const Bin = () => (
  <svg {...base}><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
);
