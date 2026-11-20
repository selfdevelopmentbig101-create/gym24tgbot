/* Line icons (24x24, stroke = currentColor), drawn to match the reference style. */
import type { ReactNode } from "react";

function Svg({ children, size = 24 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  );
}

export const ArrowLeft = () => <Svg><path d="M19 12H5M11 6l-6 6 6 6" /></Svg>;
export const Close = () => <Svg><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const Check = () => <Svg size={14}><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>;
export const Male = () => <Svg><circle cx="10" cy="14" r="5" /><path d="M14 10l6-6M15 4h5v5" /></Svg>;
export const Female = () => <Svg><circle cx="12" cy="9" r="5" /><path d="M12 14v7M9 18h6" /></Svg>;
export const Neutral = () => <Svg><circle cx="12" cy="12" r="5" /><path d="M12 3v4M12 17v4" /></Svg>;
export const Flame = () => (
  <Svg><path d="M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2.2 1.2-3.7 2.3-4.8.3 1.6 1.2 2.6 2.2 2.8C11 8.6 11 5.5 12 3z" /></Svg>
);
export const Drumstick = () => (
  <Svg><path d="M15.5 4.5a4.6 4.6 0 0 1 0 6.5c-1.4 1.4-3.3 1.6-4.6 1.3L8 15.2a1.8 1.8 0 1 1-2.6 2.6 1.8 1.8 0 1 1-1.4-3l2.9-2.9c-.3-1.3-.1-3.2 1.3-4.6a4.6 4.6 0 0 1 6.5 0" /></Svg>
);
export const Bread = () => (
  <Svg><path d="M6 20V11a3 3 0 0 1-1-5.5C6 4.5 8.5 4 12 4s6 .5 7 1.5A3 3 0 0 1 18 11v9z" /><path d="M10 10.5v.01M14 13v.01M11 15.5v.01" /></Svg>
);
export const Drop = () => <Svg><path d="M12 3.5l5.2 7.3a6.3 6.3 0 1 1-10.4 0z" /></Svg>;
export const TrendUp = () => <Svg><path d="M4 17l6-6 4 4 6-7M15 8h5v5" /></Svg>;
export const TrendDown = () => <Svg><path d="M4 7l6 6 4-4 6 7M15 16h5v-5" /></Svg>;
export const Heart = () => <Svg><path d="M12 20s-7-4.4-7-9.2A3.8 3.8 0 0 1 12 8a3.8 3.8 0 0 1 7 2.8C19 15.6 12 20 12 20z" /></Svg>;
export const Leaf = () => <Svg><path d="M5 19c0-8 5-13 14-14-1 9-6 14-14 14zM5 19l7-7" /></Svg>;
export const Scale = () => <Svg><rect x="4" y="4" width="16" height="16" rx="4" /><path d="M8.5 11a3.5 3.5 0 0 1 7 0M12 11l1.6-2.2" /></Svg>;
export const Sparkles = () => (
  <Svg size={18}><path d="M10 4l1.6 4.4L16 10l-4.4 1.6L10 16l-1.6-4.4L4 10l4.4-1.6zM18 14l.8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8z" /></Svg>
);

/** Winding road illustration for the goal-date card. */
export function Road() {
  return (
    <svg width="84" height="64" viewBox="0 0 84 64" fill="none" aria-hidden>
      <defs>
        <linearGradient id="road" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--color-mint)" />
          <stop offset="1" stopColor="var(--color-lime)" />
        </linearGradient>
      </defs>
      <path d="M58 6c16 0 18 14 4 18L22 34C6 38 8 58 26 58h44" stroke="url(#road)" strokeWidth="14"
            strokeLinecap="round" />
      <path d="M58 6c16 0 18 14 4 18L22 34C6 38 8 58 26 58h44" stroke="var(--color-bg)" strokeWidth="1.5"
            strokeDasharray="4 5" strokeLinecap="round" />
    </svg>
  );
}

export const Home = () => <Svg><path d="M4 11l8-6.5 8 6.5V20h-5v-5.5H9V20H4z" /></Svg>;
export const Dumbbell = () => (
  <Svg><path d="M6.5 8v8M17.5 8v8M3.5 10v4M20.5 10v4M6.5 12h11" /></Svg>
);
export const Search = () => <Svg size={20}><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4 4" /></Svg>;
export const Sliders = () => (
  <Svg size={20}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></Svg>
);
export const ChevronRight = () => <Svg size={18}><path d="M9 6l6 6-6 6" /></Svg>;
export const Info = () => <Svg size={20}><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 8v.01" /></Svg>;
export const Swap = () => <Svg size={20}><path d="M7 7h11l-3-3M17 17H6l3 3" /></Svg>;
