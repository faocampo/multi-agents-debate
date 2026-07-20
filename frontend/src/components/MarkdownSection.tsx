import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownSectionProps {
  content: string | null;
  pendingLabel?: string;
  previewChars?: number;
}

const DEFAULT_PREVIEW_CHARS = 800;

function previewFor(content: string, limit: number): string {
  if (content.length <= limit) return content;

  const paragraphs = content.split(/\n\s*\n/);
  let length = 0;
  let i = 0;
  for (const paragraph of paragraphs) {
    if (length + paragraph.length > limit && i > 0) break;
    length += paragraph.length + 2;
    i++;
  }

  if (i === 0) {
    const slice = content.slice(0, limit);
    const lastSpace = slice.lastIndexOf(" ");
    return slice.slice(0, lastSpace > 0 ? lastSpace : limit);
  }

  return paragraphs.slice(0, i).join("\n\n");
}

export function MarkdownSection({
  content,
  pendingLabel = "Waiting for this stage…",
  previewChars = DEFAULT_PREVIEW_CHARS,
}: MarkdownSectionProps) {
  const [expanded, setExpanded] = useState(false);
  const preview = useMemo(() => (content ? previewFor(content, previewChars) : ""), [content, previewChars]);

  if (!content) return <p className="pending-copy">{pendingLabel}</p>;

  const isLong = content.length > previewChars;
  return (
    <div className="markdown-section">
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
          {expanded ? content : preview}
        </ReactMarkdown>
      </div>
      {isLong && (
        <button
          type="button"
          className="expand-button"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
