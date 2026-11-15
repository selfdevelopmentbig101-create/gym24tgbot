/* Extra line icons for the Plan screens (same style as Icons.tsx: stroke = currentColor). */
import type { ReactNode } from "react";

function Svg({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  );
}

export const Calendar = () => (
  <Svg size={24}><rect x="4" y="5" width="16" height="15" rx="3" /><path d="M8 3v4M16 3v4M4 10h16" /></Svg>
);
export const ChevronLeft = () => <Svg size={18}><path d="M15 6l-6 6 6 6" /></Svg>;
export const Bolt = () => <Svg size={18}><path d="M13 3L5 13h6l-1 8 8-10h-6z" /></Svg>;
export const Warn = () => <Svg><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17v.01" /></Svg>;
export const Pencil = () => <Svg size={18}><path d="M4 20l4-1 11-11-3-3L5 16z" /><path d="M14 6l3 3" /></Svg>;
export const ArrowUp = () => <Svg size={18}><path d="M12 19V5M6 11l6-6 6 6" /></Svg>;
export const ArrowDown = () => <Svg size={18}><path d="M12 5v14M6 13l6 6 6-6" /></Svg>;
export const Trash = () => <Svg size={18}><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12" /></Svg>;
export const Plus = () => <Svg size={18}><path d="M12 5v14M5 12h14" /></Svg>;
