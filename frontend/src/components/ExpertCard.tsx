import type { ExpertOpinion, RoleSpec } from "../types";
import { MarkdownSection } from "./MarkdownSection";

interface ExpertCardProps {
  role: RoleSpec;
  opinion?: ExpertOpinion;
  debate: boolean;
  challenge: boolean;
  index: number;
}

export function ExpertCard({ role, opinion, debate, challenge, index }: ExpertCardProps) {
  return (
    <article className="expert-card" style={{ "--role-index": index } as React.CSSProperties}>
      <header>
        <span className="role-number">0{index + 1}</span>
        <div>
          <p className="eyebrow">{role.focus}</p>
          <h3>{role.name}</h3>
        </div>
      </header>
      <p className="role-bias">Default lens: {role.bias}</p>
      <div className="expert-analysis">
        <p className="section-kicker">
          {challenge ? "Independent reconsideration" : "Independent analysis"}
        </p>
        <MarkdownSection content={opinion?.initial_analysis ?? null} />
      </div>
      {debate && (
        <div className="rebuttal-analysis">
          <p className="section-kicker">
            {challenge ? "Response after challenge debate" : "Response after debate"}
          </p>
          <MarkdownSection content={opinion?.rebuttal ?? null} pendingLabel="Waiting for debate..." />
        </div>
      )}
      {challenge && (
        <div className="rebuttal-analysis">
          <p className="section-kicker">Response to advocate</p>
          <MarkdownSection
            content={opinion?.advocate_response ?? null}
            pendingLabel="Waiting for advocate response..."
          />
        </div>
      )}
    </article>
  );
}
