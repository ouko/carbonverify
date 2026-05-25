import DOMPurify from 'dompurify';

interface SafeHtmlProps {
  html: string;
  className?: string;
  tag?: keyof JSX.IntrinsicElements;
}

/**
 * Render HTML safely by sanitizing through DOMPurify.
 * Use this for any user-generated or untrusted HTML content.
 */
export function SafeHtml({ html, className, tag: Tag = 'div' }: SafeHtmlProps) {
  const sanitized = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li'],
    ALLOWED_ATTR: ['href', 'target', 'rel'],
  });

  return <Tag className={className} dangerouslySetInnerHTML={{ __html: sanitized }} />;
}
