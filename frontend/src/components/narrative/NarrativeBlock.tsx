/** 叙事正文渲染：把 DM 输出的轻量 Markdown（标题/列表/引用/表格/加粗斜体）转成 JSX。
 *
 * 从 `NarrativeStream.tsx` 拆出（那边只留滚动容器与消息列表）。
 */
function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|~~[^~]+~~)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-ink-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={i} className="italic text-ink-700">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('~~') && part.endsWith('~~')) {
      return <span key={i} className="line-through text-ink-400">{part.slice(2, -2)}</span>;
    }
    return <span key={i}>{part}</span>;
  });
}

/** 渲染一段叙事文本，支持 Markdown 常见块级结构 */
export default function NarrativeBlock({ text }: { text: string }) {
  const paragraphs = text.replace(/\r\n/g, '\n').split(/\n\s*\n/).filter((p) => p.trim());
  return (
    <div className="narrative-prose">
      {paragraphs.map((p, i) => {
        const trimmed = p.trim();
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
          return <hr key={i} className="my-3 border-ink-200" />;
        }
        if (trimmed.startsWith('### ')) {
          return <h4 key={i} className="text-sm font-bold text-ink-900 mt-1 mb-1.5">{renderInline(trimmed.slice(4))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={i} className="text-base font-bold text-ink-900 mt-1 mb-1.5">{renderInline(trimmed.slice(3))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={i} className="text-lg font-bold text-ink-900 mt-1 mb-2">{renderInline(trimmed.slice(2))}</h2>;
        }
        const lines = trimmed.split('\n');

        // 引用块
        if (lines.every((l) => /^\s*>\s?/.test(l))) {
          return (
            <blockquote
              key={i}
              className="border-l-[3px] border-brand-300 bg-brand-50/60 rounded-r-xl px-3.5 py-2.5 text-ink-600 text-sm leading-relaxed mb-3"
            >
              {lines.map((l, j) => (
                <p key={j} className={j > 0 ? 'mt-1' : ''}>{renderInline(l.replace(/^\s*>\s?/, ''))}</p>
              ))}
            </blockquote>
          );
        }

        // 无序列表
        if (lines.every((l) => /^\s*[-*+]\s+/.test(l))) {
          return (
            <ul key={i} className="space-y-1 pl-5 list-disc marker:text-ink-400 mb-3">
              {lines.map((l, j) => (
                <li key={j} className="text-ink-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*[-*+]\s+/, ''))}</li>
              ))}
            </ul>
          );
        }

        // 有序列表
        if (lines.every((l) => /^\s*\d+[.)]\s+/.test(l))) {
          return (
            <ol key={i} className="space-y-1 pl-5 list-decimal marker:text-ink-400 mb-3">
              {lines.map((l, j) => (
                <li key={j} className="text-ink-700 text-sm leading-relaxed">{renderInline(l.replace(/^\s*\d+[.)]\s+/, ''))}</li>
              ))}
            </ol>
          );
        }

        // 简易表格：至少两行，且第二行是分隔行
        const tableLines = lines.filter((l) => l.includes('|'));
        if (tableLines.length >= 2 && /^\s*\|?[\s:|-]+\|?\s*$/.test(tableLines[1])) {
          const parseRow = (row: string) => row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
          const head = parseRow(tableLines[0]);
          const body = tableLines.slice(2);
          return (
            <div key={i} className="mb-3 overflow-x-auto border border-ink-200 rounded-xl">
              <table className="w-full text-left text-xs">
                <thead className="bg-ink-50">
                  <tr>
                    {head.map((h, j) => (
                      <th key={j} className="px-2.5 py-2 font-semibold text-ink-700 border-b border-ink-200 whitespace-nowrap">{renderInline(h)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, r) => (
                    <tr key={r} className="even:bg-ink-50/40">
                      {parseRow(row).map((c, j) => (
                        <td key={j} className="px-2.5 py-2 text-ink-600 border-b border-ink-100 last:border-0">{renderInline(c)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        return (
          <p key={i} className="mb-3 last:mb-0 whitespace-pre-line">{renderInline(trimmed)}</p>
        );
      })}
    </div>
  );
}
