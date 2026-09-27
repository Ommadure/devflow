/** "React Hooks, timing ,, " → ["react-hooks", "timing"] (the server normalises the same way). */
export function parseTags(input: string): string[] {
  const tags = input
    .split(",")
    .map((tag) => tag.trim().toLowerCase().split(/\s+/).join("-"))
    .filter(Boolean);
  return [...new Set(tags)];
}
