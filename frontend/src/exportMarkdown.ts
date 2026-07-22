import type { RunRecord } from "./types";

function opinionFor(run: RunRecord, roleName: string) {
  return run.expert_opinions.find((opinion) => opinion.role.name === roleName);
}

export function markdownFilename(run: RunRecord): string {
  const date = run.created_at.slice(0, 10);
  const shortId = run.id.replaceAll("-", "").slice(0, 8);
  return `swarm-analysis-${date}-${shortId}.md`;
}

export function serializeRunToMarkdown(run: RunRecord): string {
  const lines: string[] = [
    "# AI Swarm Analysis",
    "",
    "## Decision",
    "",
    run.decision,
    "",
    "## Run metadata",
    "",
    `- Run ID: \`${run.id}\``,
    `- Created: ${run.created_at}`,
    `- Completed: ${run.completed_at ?? "In progress"}`,
    `- Status: ${run.status}`,
    `- Debate: ${run.debate ? "Enabled" : "Disabled"}`,
    `- Root run ID: ${run.root_run_id ?? "None"}`,
    `- Parent run ID: ${run.parent_run_id ?? "None"}`,
    "",
  ];

  if (run.challenge) {
    lines.push(
      "## Challenge",
      "",
      `- Type: ${run.challenge.kind}`,
      `- Input: ${run.challenge.input}`,
      `- Parent run ID: \`${run.challenge.parent_run_id}\``,
      "",
      "### Parent conclusion",
      "",
      run.challenge.parent_conclusion,
      "",
    );
  }

  if (run.clarifying_questions.length > 0 && !run.clarification_skipped) {
    lines.push("## Clarifying Q&A", "");
    run.clarifying_questions.forEach((question, index) => {
      lines.push(
        `**Q:** ${question}`,
        "",
        `**A:** ${run.clarifying_answers?.[index] ?? "Pending."}`,
        "",
      );
    });
  }

  lines.push(
    "## The panel",
    "",
  );

  if (run.roles.length === 0) lines.push("Pending.", "");
  run.roles.forEach((role, index) => {
    const opinion = opinionFor(run, role.name);
    lines.push(
      `### ${index + 1}. ${role.name}`,
      "",
      `- Focus: ${role.focus}`,
      `- Deliberate bias: ${role.bias}`,
      "",
      run.challenge ? "#### Independent reconsideration" : "#### Initial analysis",
      "",
      opinion?.initial_analysis ?? "Pending.",
      "",
    );
    if (run.debate) {
      lines.push(
        run.challenge ? "#### Challenge peer debate" : "#### Rebuttal",
        "",
        opinion?.rebuttal ?? "Pending.",
        "",
      );
    }
    if (run.challenge) {
      lines.push(
        "#### Response to advocate",
        "",
        opinion?.advocate_response ?? "Pending.",
        "",
      );
    }
  });

  lines.push(
    "## Devil's advocate",
    "",
    run.advocate_analysis ?? "Pending.",
    "",
    "## Final synthesis",
    "",
    run.synthesis ?? "Pending.",
    "",
  );

  if (run.error) {
    lines.push(
      "## Run error",
      "",
      `- Stage: ${run.error.stage}`,
      `- Code: \`${run.error.code}\``,
      `- Message: ${run.error.message}`,
      "",
    );
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

export function downloadRunMarkdown(run: RunRecord): void {
  const blob = new Blob([serializeRunToMarkdown(run)], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = markdownFilename(run);
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
