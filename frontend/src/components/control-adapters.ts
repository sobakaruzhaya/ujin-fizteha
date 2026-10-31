import type { ComponentType, ReactNode } from "react";
import SelectSource from "./reactbits/GlideSelect";
import ScrubSource from "./reactbits/ScrubField";
import SwitchSource from "./reactbits/SquishSwitch";
import ListSource from "./reactbits/AnimatedList";

// Typed boundaries around the upstream JavaScript component APIs.
export const GlideSelect = SelectSource as unknown as ComponentType<{
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  ariaLabel: string;
  disabled?: boolean;
  showTags?: boolean;
  surfaceColor?: string;
  highlightColor?: string;
  accentColor?: string;
  menuWidth?: number;
  className?: string;
}>;
export const ScrubField = ScrubSource as unknown as ComponentType<{
  label: string;
  suffix: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  accent?: string;
  chipColor?: string;
  disabled?: boolean;
  showDelta?: boolean;
  showFill?: boolean;
}>;
export const SquishSwitch = SwitchSource as unknown as ComponentType<{
  checked: boolean;
  onChange: (value: boolean) => void;
  ariaLabel: string;
  disabled?: boolean;
  width?: number;
  height?: number;
  trackOnColor?: string;
  thumbOnColor?: string;
}>;
export const AnimatedList = ListSource as unknown as ComponentType<{
  items: { id: string }[];
  renderItem: (item: { id: string }, index: number) => ReactNode;
  interactive?: boolean;
  frame?: boolean;
  showGradients?: boolean;
  enableArrowNavigation?: boolean;
  selectOnHover?: boolean;
  width?: string;
  maxHeight?: string;
  animation?: string;
  className?: string;
}>;
