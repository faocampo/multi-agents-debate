import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MarkdownSection } from "../components/MarkdownSection";

describe("MarkdownSection", () => {
  it("renders Markdown and discards raw HTML", () => {
    const { container } = render(
      <MarkdownSection content={"**Visible**\n\n<script>window.bad = true</script>"} />,
    );

    expect(screen.getByText("Visible")).toHaveStyle({ fontWeight: "bold" });
    expect(container.querySelector("script")).toBeNull();
    expect(screen.queryByText("window.bad = true")).toBeNull();
  });
});

