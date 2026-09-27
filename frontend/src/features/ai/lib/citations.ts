/**
 * Turn the model's "[2]" citations into markdown links to "#source-2", so the renderer can
 * make them clickable. Only numbers that match a real source become links: a model that
 * cites [7] from six sources gets plain text, not a broken link.
 */
export function linkCitations(text: string, sourceCount: number): string {
  return text.replace(/\[(\d+)\](?!\()/g, (whole, digits: string) => {
    const n = Number(digits);
    return n >= 1 && n <= sourceCount ? `[${n}](#source-${n})` : whole;
  });
}
