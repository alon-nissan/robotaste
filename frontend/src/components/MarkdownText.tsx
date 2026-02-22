import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownTextProps {
  content: string;
  className?: string;
}

/**
 * Renders markdown text with consistent styling matching the design system.
 * Handles bold, italic, lists, paragraphs, and other common markdown syntax.
 */
export function MarkdownText({ content, className = '' }: MarkdownTextProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
        // Paragraphs: inherit text sizing from parent, add spacing
        p: ({ children }) => (
          <p className="leading-relaxed mb-4 last:mb-0">{children}</p>
        ),
        // Strong/bold: use semibold weight
        strong: ({ children }) => (
          <strong className="font-semibold">{children}</strong>
        ),
        // Emphasis/italic: use italic style
        em: ({ children }) => (
          <em className="italic">{children}</em>
        ),
        // Unordered lists: add spacing and bullets
        ul: ({ children }) => (
          <ul className="list-disc list-inside mb-4 last:mb-0 space-y-2">{children}</ul>
        ),
        // Ordered lists: add spacing and numbers
        ol: ({ children }) => (
          <ol className="list-decimal list-inside mb-4 last:mb-0 space-y-2">{children}</ol>
        ),
        // List items: inherit spacing from parent
        li: ({ children }) => (
          <li className="leading-relaxed">{children}</li>
        ),
        // Headings (in case protocol text includes them)
        h1: ({ children }) => (
          <h1 className="text-2xl font-semibold mb-4">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-xl font-semibold mb-3">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-lg font-semibold mb-2">{children}</h3>
        ),
      }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
