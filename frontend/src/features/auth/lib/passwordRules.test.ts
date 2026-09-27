import { describe, expect, it } from "vitest";
import { meetsPasswordRules, passwordStrength } from "./passwordRules";

describe("password rules", () => {
  it.each([
    ["Correct-Horse-9", true],
    ["Short1A", false],
    ["alllowercase1", false],
    ["ALLUPPERCASE1", false],
    ["NoDigitsHere", false],
    ["A1" + "a".repeat(127), false], // over 128
  ])("%s → %s", (password, ok) => {
    expect(meetsPasswordRules(password)).toBe(ok);
  });

  it("scores 0 to 6", () => {
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("abc")).toBe(1);
    expect(passwordStrength("Abcdefg1")).toBe(4);
    expect(passwordStrength("Abcdefgh1234!")).toBe(6);
  });
});
