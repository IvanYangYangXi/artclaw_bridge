// Lightweight markdown renderer for chat messages
// Supports: tables, code blocks, inline code, bold, italic, headers, hr, lists, links
import { cn } from '../../utils/cn'

interface MarkdownRendererProps {
  content: string
  className?: string
}

/** Parse a markdown table block (header + separator + rows) into JSX */
function renderTable(lines: string[]): React.ReactNode {
  const parseRow = (line: string) =>
    line.replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())

  const headers = parseRow(lines[0])
  // lines[1] is separator (---), parse alignment
  const aligns = parseRow(lines[1]).map((sep) => {
    if (sep.startsWith(':') && sep.endsWith(':')) return 'center' as const
    if (sep.endsWith(':')) return 'right' as const
    return 'left' as const
  })
  const rows = lines.slice(2).map(parseRow)

  return (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full text-[12px] border-collapse">
        <thead>
          <tr className="border-b border-gray-600">
            {headers.map((h, i) => (
              <th
                key={i}
                style={{ textAlign: aligns[i] || 'left' }}
                className="px-3 py-1.5 text-text-primary font-semibold bg-bg-tertiary/40"
              >
                {renderInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-gray-700/50 hover:bg-bg-tertiary/20">
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  style={{ textAlign: aligns[ci] || 'left' }}
                  className="px-3 py-1 text-text-secondary"
                >
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Render inline markdown: bold, italic, inline code, links */
function renderInline(text: string): React.ReactNode {
  if (!text) return null

  // Split by inline code first to avoid processing markdown inside code spans
  const parts: React.ReactNode[] = []
  const codeRegex = /`([^`]+)`/g
  let lastIdx = 0
  let match: RegExpExecArray | null

  while ((match = codeRegex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(...renderFormattedText(text.slice(lastIdx, match.index)))
    }
    parts.push(
      <code key={`c${match.index}`} className="px-1 py-0.5 rounded text-[12px] bg-gray-800 text-orange-300 font-mono">
        {match[1]}
      </code>,
    )
    lastIdx = match.index + match[0].length
  }
  if (lastIdx < text.length) {
    parts.push(...renderFormattedText(text.slice(lastIdx)))
  }
  return <>{parts}</>
}

/** Render bold, italic, links in a non-code segment */
function renderFormattedText(text: string): React.ReactNode[] {
  // Process bold+italic, bold, italic, links
  const tokens: React.ReactNode[] = []
  // Combined regex for **bold**, *italic*, [text](url)
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\(([^)]+)\))/g
  let last = 0
  let m: RegExpExecArray | null
  let ki = 0

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) tokens.push(text.slice(last, m.index))
    if (m[2]) {
      // bold
      tokens.push(<strong key={`b${ki++}`}>{m[2]}</strong>)
    } else if (m[3]) {
      // italic
      tokens.push(<em key={`i${ki++}`}>{m[3]}</em>)
    } else if (m[4] && m[5]) {
      // link
      tokens.push(
        <a key={`a${ki++}`} href={m[5]} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
          {m[4]}
        </a>,
      )
    }
    last = m.index + m[0].length
  }
  if (last < text.length) tokens.push(text.slice(last))
  return tokens
}

/** Check if a line is a table separator like |---|:---:|---:| */
function isTableSeparator(line: string): boolean {
  return /^\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?$/.test(line.trim())
}

export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  if (!content) return null

  const lines = content.split('\n')
  const elements: React.ReactNode[] = []
  let i = 0
  let key = 0

  while (i < lines.length) {
    const line = lines[i]

    // --- Code block ---
    if (line.trimStart().startsWith('```')) {
      const lang = line.trimStart().slice(3).trim()
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].trimStart().startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      elements.push(
        <div key={key++} className="my-2 rounded bg-gray-800/80 border border-gray-700 overflow-hidden">
          {lang && (
            <div className="px-3 py-1 text-[11px] text-gray-500 border-b border-gray-700/50">{lang}</div>
          )}
          <pre className="px-3 py-2 text-[12px] font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">
            {codeLines.join('\n')}
          </pre>
        </div>,
      )
      continue
    }

    // --- Table ---
    if (i + 1 < lines.length && line.includes('|') && isTableSeparator(lines[i + 1])) {
      const tableLines: string[] = [line, lines[i + 1]]
      i += 2
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        tableLines.push(lines[i])
        i++
      }
      elements.push(<div key={key++}>{renderTable(tableLines)}</div>)
      continue
    }

    // --- Headers ---
    const h3 = line.match(/^###\s+(.+)/)
    if (h3) {
      elements.push(<h4 key={key++} className="text-[13px] font-semibold text-text-primary mt-2 mb-1">{renderInline(h3[1])}</h4>)
      i++; continue
    }
    const h2 = line.match(/^##\s+(.+)/)
    if (h2) {
      elements.push(<h3 key={key++} className="text-[14px] font-semibold text-text-primary mt-2 mb-1">{renderInline(h2[1])}</h3>)
      i++; continue
    }
    const h1 = line.match(/^#\s+(.+)/)
    if (h1) {
      elements.push(<h2 key={key++} className="text-[15px] font-bold text-text-primary mt-2 mb-1">{renderInline(h1[1])}</h2>)
      i++; continue
    }

    // --- HR ---
    if (/^-{3,}$/.test(line.trim())) {
      elements.push(<hr key={key++} className="border-gray-700 my-2" />)
      i++; continue
    }

    // --- Unordered list ---
    if (/^\s*[-*]\s+/.test(line)) {
      const listItems: React.ReactNode[] = []
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*[-*]\s+/, '')
        listItems.push(<li key={listItems.length} className="ml-4 text-text-primary">{renderInline(itemText)}</li>)
        i++
      }
      elements.push(<ul key={key++} className="list-disc ml-2 my-1 text-[13px]">{listItems}</ul>)
      continue
    }

    // --- Ordered list ---
    if (/^\s*\d+\.\s+/.test(line)) {
      const listItems: React.ReactNode[] = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        const itemText = lines[i].replace(/^\s*\d+\.\s+/, '')
        listItems.push(<li key={listItems.length} className="ml-4 text-text-primary">{renderInline(itemText)}</li>)
        i++
      }
      elements.push(<ol key={key++} className="list-decimal ml-2 my-1 text-[13px]">{listItems}</ol>)
      continue
    }

    // --- Empty line ---
    if (line.trim() === '') {
      elements.push(<div key={key++} className="h-2" />)
      i++; continue
    }

    // --- Normal paragraph ---
    elements.push(
      <p key={key++} className="text-[13px] text-text-primary leading-relaxed">
        {renderInline(line)}
      </p>,
    )
    i++
  }

  return <div className={cn('space-y-0.5', className)}>{elements}</div>
}
