import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownSectionProps {
  content: string | null;
  pendingLabel?: string;
}

export function MarkdownSection({
  content,
  pendingLabel = "Waiting for this stage…",
}: MarkdownSectionProps) {
  if (!content) return <p className="pending-copy">{pendingLabel}</p>;
  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

