import { describe, expect, it } from "vitest";
import { markdownFilename, serializeRunToMarkdown } from "../exportMarkdown";
import { completedRun } from "./fixtures";

describe("Markdown export", () => {
  it("serializes every completed section in deterministic order", () => {
    const markdown = serializeRunToMarkdown(completedRun);

    expect(markdownFilename(completedRun)).toBe("swarm-analysis-2026-07-19-c60c3906.md");
    expect(markdown).toContain("# AI Swarm Analysis");
    expect(markdown).toContain("## Independent analyses");
    expect(markdown).toContain("## Debate rebuttals");
    expect(markdown).toContain("## Devil's advocate");
    expect(markdown).toContain("## Final synthesis");
    expect(markdown.endsWith("\n")).toBe(true);
    expect(markdown.endsWith("\n\n")).toBe(false);
  });

  it("omits debate and adds safe failure details", () => {
    const markdown = serializeRunToMarkdown({
      ...completedRun,
      debate: false,
      status: "failed",
      stage: "failed",
      error: {
        stage: "devils_advocate",
        code: "provider_timeout",
        message: "Provider timed out.",
        retryable: true,
      },
    });

    expect(markdown).not.toContain("## Debate rebuttals");
    expect(markdown).toContain("## Run error");
    expect(markdown).toContain("`provider_timeout`");
  });
});

