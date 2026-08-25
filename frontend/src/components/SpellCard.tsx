/** 法术卡：默认只显示一行摘要（火球术：三环 塑能），点开显示完整详情。 */

export interface SpellData {
  name: string;
  level: string;
  school?: string;
  description?: string;
  casting_time?: string;
  range?: string;
  components?: string;
  duration?: string;
  classes?: string[] | string;
  ritual?: boolean;
  prepared?: boolean;
  name_zh?: string;
  description_zh?: string;
}

function ringLabel(level: string): string {
  const n = Number(level);
  if (Number.isFinite(n) && n === 0) return '戏法';
  return `${level}环`;
}

export default function SpellCard({ spell, paper = false }: { spell: SpellData; paper?: boolean }) {
  const classList = Array.isArray(spell.classes)
    ? spell.classes
    : typeof spell.classes === 'string'
      ? spell.classes.split(/[,，、]/).map(s => s.trim()).filter(Boolean)
      : [];
  const classes = classList.join('、');
  const displayName = spell.name_zh || spell.name;
  const displayDesc = spell.description_zh || spell.description || '';
  return (
    <details className={`group rounded-lg border ${paper ? 'border-amber-900/20 bg-white/70' : 'border-gray-200 bg-white'}`}>
      <summary className="cursor-pointer select-none px-2.5 py-1.5 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-gray-800">
          {displayName}：{ringLabel(spell.level)} {spell.school || '未知学派'}
          {spell.name_zh && spell.name !== spell.name_zh && <span className="text-gray-400 font-normal">（{spell.name}）</span>}
          {classes && <span className="text-gray-400 font-normal">（{classes}）</span>}
        </span>
        <span className="text-[9px] text-gray-400 shrink-0">
          {spell.ritual ? '仪式 · ' : ''}{spell.prepared === false ? '未准备' : ''}
          <span className="ml-1 group-open:hidden">▸</span>
          <span className="ml-1 hidden group-open:inline">▾</span>
        </span>
      </summary>
      <div className="px-2.5 pb-2 border-t border-gray-100 text-[11px] leading-relaxed text-gray-700 space-y-1">
        {spell.casting_time && <p><span className="text-gray-400">施法时间：</span>{spell.casting_time}</p>}
        {spell.range && <p><span className="text-gray-400">施法距离：</span>{spell.range}</p>}
        {spell.components && <p><span className="text-gray-400">法术成分：</span>{spell.components}</p>}
        {spell.duration && <p><span className="text-gray-400">持续时间：</span>{spell.duration}</p>}
        {displayDesc && <p className="text-gray-700 whitespace-pre-line">{displayDesc}</p>}
        {spell.description_zh && spell.description && <p className="text-gray-400 text-[10px] italic whitespace-pre-line">原文：{spell.description}</p>}
      </div>
    </details>
  );
}
