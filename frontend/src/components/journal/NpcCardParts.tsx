/** NPC 卡基础展示：字段行、数值网格与属性网格。 */
import { ATTR_NAMES } from './types';
import { textValue } from '../../utils/textValue';

export const mod = (v: number) =>
  `${Math.floor((v - 10) / 2) >= 0 ? '+' : ''}${Math.floor((v - 10) / 2)}`;

export function Row({ k, v, c }: { k: string; v?: string; c?: string }) {
  if (!v) return null;
  const hidden = v === '???';
  return (
    <div className="flex gap-1.5 text-2xs leading-relaxed">
      <span className="text-ink-400 shrink-0">{k}：</span>
      <span className={c || (hidden ? 'text-ink-400 italic' : 'text-ink-600')}>{hidden ? '???' : v}</span>
    </div>
  );
}

export function StatGrid({ npc }: { npc: any }) {
  const tiles: Array<[string, string]> = [];
  if (npc.hp != null && npc.max_hp != null) tiles.push(['HP', `${npc.hp}/${npc.max_hp}`]);
  if (npc.ac != null) tiles.push(['AC', String(npc.ac)]);
  if (npc.level != null) tiles.push(['Lv', String(npc.level)]);
  if (tiles.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-1">
      {tiles.map(([k, v]) => (
        <div key={k} className="bg-white rounded-lg px-1.5 py-1 border border-ink-200 text-center">
          <span className="text-3xs text-ink-400">{k}</span>
          <span className="ml-1 font-mono font-bold text-2xs text-ink-800">{v}</span>
        </div>
      ))}
    </div>
  );
}

export function AttrGrid({ attrs, size = 'sm' }: {
  attrs: Record<string, number>;
  size?: 'sm' | 'lg';
}) {
  const entries = Object.entries(attrs);
  if (entries.length === 0) return null;
  return (
    <div className="grid grid-cols-3 gap-x-1 gap-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="text-center leading-tight">
          <p className="text-3xs uppercase tracking-wide text-ink-400">{ATTR_NAMES[k] || k}</p>
          <p className={`font-bold ${size === 'lg' ? 'text-xs' : 'text-2xs'}`}>
            {textValue(v)}
            <span className="ml-0.5 text-3xs text-ink-400 font-normal">({mod(Number(v))})</span>
          </p>
        </div>
      ))}
    </div>
  );
}
