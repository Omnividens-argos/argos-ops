import { useMemo } from "react";

// Renderer markdown minimaliste, zéro dépendance.
//
// Cible : les drafts produits par les bots Argos (structure connue —
// frontmatter YAML + body avec headers H1-H3, paragraphes, listes, gras,
// italique, code inline, blocs de code, liens, citations). Pas conçu
// pour parser du markdown arbitraire utilisateur. ~80 LOC.
//
// Le frontmatter (entre `---`...`---`) est rendu séparément comme une card
// de métadonnées (key/value pairs).
//
// Sécurité : on s'appuie sur React qui échappe par défaut tout texte interpolé.
// Les seules balises HTML qu'on injecte viennent de nos propres helpers.

interface Props {
  /** Texte raw du markdown (frontmatter inclus). */
  content: string;
}

interface ParsedDoc {
  frontmatter: Record<string, string>;
  body: string;
}

function splitFrontmatter(text: string): ParsedDoc {
  if (!text.startsWith("---")) return { frontmatter: {}, body: text };
  const end = text.indexOf("\n---", 3);
  if (end === -1) return { frontmatter: {}, body: text };
  const block = text.slice(3, end);
  const body = text.slice(end + 4).replace(/^\n/, "");
  const frontmatter: Record<string, string> = {};
  for (const line of block.split("\n")) {
    const stripped = line.trim();
    if (!stripped || stripped.startsWith("#")) continue;
    const match = stripped.match(/^([\w-]+)\s*:\s*(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    // Strip outer quotes.
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) frontmatter[match[1]] = value;
  }
  return { frontmatter, body };
}

// =============================================================================
// Inline formatting — bold, italic, code, links — appliqué dans un paragraphe.
// =============================================================================
function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  // On gère 4 patterns par priorité : code inline (`x`) > link [text](url) >
  // bold **x** > italic *x* (mais pas conflictuel avec bold). On split itéra-
  // tivement pour éviter des regex récursives.
  // Patterns combinés en une regex unique avec groupes nommés simulés.
  const re = /(`[^`]+`)|(\[([^\]]+)\]\(([^)]+)\))|(\*\*[^*]+\*\*)|(\*[^*]+\*)/g;
  const out: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let idx = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      out.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const key = `${keyPrefix}-${idx++}`;
    if (token.startsWith("`")) {
      out.push(
        <code
          key={key}
          className="font-mono text-[11px] bg-argos-surface-2 px-1 py-0.5 rounded text-argos-fg-secondary"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("[")) {
      const label = match[3];
      const url = match[4];
      out.push(
        <a
          key={key}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-argos-info hover:underline decoration-dotted underline-offset-2"
        >
          {label}
        </a>,
      );
    } else if (token.startsWith("**")) {
      out.push(
        <strong key={key} className="font-semibold text-argos-fg">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      // italic *...*
      out.push(
        <em key={key} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    out.push(text.slice(lastIndex));
  }
  return out;
}

// =============================================================================
// Block renderer — itère ligne par ligne, regroupe paragraphes / listes / code.
// =============================================================================
function renderBlocks(body: string): React.ReactNode[] {
  const lines = body.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Blank line → skip
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Code block ```
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      i += 1; // skip closing ```
      blocks.push(
        <pre
          key={`code-${blocks.length}`}
          className="bg-argos-surface-2 border border-argos-border-subtle rounded-md p-3 overflow-x-auto"
        >
          <code className="font-mono text-[11.5px] text-argos-fg-secondary whitespace-pre">
            {lang && (
              <div className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-tertiary mb-1.5">
                {lang}
              </div>
            )}
            {codeLines.join("\n")}
          </code>
        </pre>,
      );
      continue;
    }

    // Headers (h1/h2/h3)
    const headerMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const text = headerMatch[2];
      const classes = {
        1: "text-lg font-semibold text-argos-fg mt-4 mb-2",
        2: "text-base font-semibold text-argos-fg mt-4 mb-2",
        3: "text-sm font-semibold text-argos-fg mt-3 mb-1.5",
      } as const;
      const Tag = (`h${level}` as "h1" | "h2" | "h3");
      const className = classes[level as 1 | 2 | 3];
      blocks.push(
        <Tag key={`h-${blocks.length}`} className={className}>
          {renderInline(text, `h-${blocks.length}`)}
        </Tag>,
      );
      i += 1;
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      const quoteLines: string[] = [line.slice(2)];
      i += 1;
      while (i < lines.length && lines[i].startsWith("> ")) {
        quoteLines.push(lines[i].slice(2));
        i += 1;
      }
      blocks.push(
        <blockquote
          key={`q-${blocks.length}`}
          className="border-l-2 border-argos-info pl-3 py-1 my-2 text-argos-fg-secondary italic"
        >
          {renderInline(quoteLines.join(" "), `q-${blocks.length}`)}
        </blockquote>,
      );
      continue;
    }

    // List (unordered with `-` or `*`)
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ul
          key={`ul-${blocks.length}`}
          className="list-disc list-outside pl-5 space-y-1 text-argos-fg-secondary"
        >
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item, `ul-${blocks.length}-${idx}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    // List (ordered with `1.` etc)
    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      blocks.push(
        <ol
          key={`ol-${blocks.length}`}
          className="list-decimal list-outside pl-5 space-y-1 text-argos-fg-secondary"
        >
          {items.map((item, idx) => (
            <li key={idx}>{renderInline(item, `ol-${blocks.length}-${idx}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(line.trim())) {
      blocks.push(
        <hr
          key={`hr-${blocks.length}`}
          className="my-4 border-argos-border-subtle"
        />,
      );
      i += 1;
      continue;
    }

    // Paragraph — consomme lignes consécutives non-vides non-spéciales
    const paraLines: string[] = [line];
    i += 1;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !lines[i].startsWith("#") &&
      !lines[i].startsWith("```") &&
      !lines[i].startsWith("> ") &&
      !/^[-*]\s+/.test(lines[i]) &&
      !/^\d+\.\s+/.test(lines[i]) &&
      !/^[-*_]{3,}$/.test(lines[i].trim())
    ) {
      paraLines.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p
        key={`p-${blocks.length}`}
        className="text-sm text-argos-fg-secondary leading-relaxed"
      >
        {renderInline(paraLines.join(" "), `p-${blocks.length}`)}
      </p>,
    );
  }

  return blocks;
}

// =============================================================================
// Public component
// =============================================================================
export function MarkdownPreview({ content }: Props) {
  const { frontmatter, body } = useMemo(() => splitFrontmatter(content), [content]);
  const blocks = useMemo(() => renderBlocks(body), [body]);
  const fmEntries = Object.entries(frontmatter);

  return (
    <div className="space-y-4">
      {fmEntries.length > 0 && (
        <div className="rounded-md border border-argos-border-subtle bg-argos-bg/40 p-3">
          <div className="font-mono text-[9px] uppercase tracking-widest text-argos-fg-tertiary mb-2">
            Frontmatter YAML
          </div>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 font-mono text-[11px]">
            {fmEntries.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-argos-fg-tertiary">{k}</dt>
                <dd className="text-argos-fg-secondary break-words">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      <div className="space-y-3">{blocks}</div>
    </div>
  );
}
