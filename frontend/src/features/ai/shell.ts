/**
 * The part of the AI feature the always-loaded app shell needs. A separate entry point on
 * purpose: importing the full barrel from the layout pulled the markdown renderer (for the
 * explain/ask panels) into the main bundle — 514 kB instead of 351 kB on every page load.
 */
export { AiUsageBadge } from "./components/AiUsageBadge";
