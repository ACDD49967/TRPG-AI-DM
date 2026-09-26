/** NPC 卡片：未完全揭示信息 / 完全揭示的官方卡片样式。 */
import { CAT_COLORS, CAT_LABELS, type NpcView } from './types';
import { textValue } from '../../utils/textValue';
import { AttrGrid, Row, StatGrid } from './NpcCardParts';
import InlineEdit from '../ui/InlineEdit';
import { useGameStore } from '../../store/gameStore';

export default function NpcCard({ npc, cat }: { npc: NpcView; cat: string }) {
  const sessionId = useGameStore((s) => s.sessionId);
  const username = useGameStore((s) => s.status.username || '');

  /** 走与 DM 工具同一个世界状态接口：update_npc / remove_npc。 */
  const applyWorldChange = async (action: string, changes?: Record<string, unknown>) => {
    if (!sessionId) return false;
    try {
      const r = await fetch(
        `/api/game/${sessionId}/world?username=${encodeURIComponent(username || 'default')}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, target: npc.name, changes: changes || {}, reason: '玩家笔记修改' }),
        });
      if (!r.ok) return false;
      try { window.dispatchEvent(new Event('dnd:journal-refresh')); } catch { /* 忽略 */ }
      return true;
    } catch {
      return false;
    }
  };

  return (
    <details className={`group rounded-xl border p-2 ${CAT_COLORS[cat] || CAT_COLORS.neutral} text-xs mb-1`}>
      <summary className="cursor-pointer select-none">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            {npc.image_path ? (
              <img src={npc.image_path} alt={npc.name} loading="lazy" className="w-6 h-6 rounded-md object-cover border border-ink-200 shrink-0" />
            ) : (
              <span className="w-1.5 h-1.5 rounded-full bg-current opacity-40 shrink-0" aria-hidden />
            )}
            <span className="font-bold text-ink-800 truncate">{npc.name}</span>
            {npc.importance === 'major' && <span className="tag-amber shrink-0">重要</span>}
          </div>
          <span className="text-2xs text-ink-400 shrink-0 flex items-center gap-1">
            {npc.hp != null && npc.max_hp != null && <span className="font-mono">HP {npc.hp}/{npc.max_hp}</span>}
            {npc.ac != null && <span className="font-mono">AC {npc.ac}</span>}
            <svg viewBox="0 0 20 20" fill="none" className="w-3 h-3 transition-transform group-open:rotate-180" aria-hidden>
              <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        </div>
      </summary>

      <div className="flex justify-end items-center gap-2 mt-2">
        <InlineEdit
          label="编辑 NPC"
          fields={[
            { key: 'role', label: '身份', value: npc.role || '' },
            { key: 'location', label: '位置', value: npc.location || '' },
            { key: 'attitude', label: '态度', value: npc.attitude || '' },
            { key: 'hp', label: 'HP', value: String(npc.hp ?? ''), type: 'number' },
            { key: 'ac', label: 'AC', value: String(npc.ac ?? ''), type: 'number' },
          ]}
          onSave={async (values) => {
            const changes: Record<string, unknown> = {};
            for (const [k, v] of Object.entries(values)) {
              if (String(v ?? '').trim() === '') continue;
              changes[k] = (k === 'hp' || k === 'ac') ? Number(v) : v;
            }
            await applyWorldChange('update_npc', changes);
          }}
        >
          <span className="text-[10px] text-ink-500">编辑身份 / 位置 / 态度 / HP / AC</span>
        </InlineEdit>
        <button
          type="button"
          className="text-[10px] text-red-600 hover:text-red-700 shrink-0"
          onClick={async () => {
            if (!window.confirm(`确定从冒险笔记移除「${npc.name}」？`)) return;
            await applyWorldChange('remove_npc');
          }}
        >
          移除
        </button>
      </div>

      {!npc.fully_revealed ? (
        <div className="mt-2 pt-2 border-t border-ink-200/70 space-y-1.5">
          <Row k="身份" v={npc.role} />
          {npc.race && npc.race !== '???' && <Row k="种族" v={npc.race} />}
          {npc.location && <Row k="位置" v={npc.location} />}
          {npc.conditions && npc.conditions.length > 0 && (
            <p className="text-2xs">
              <span className="font-bold text-ink-500">状态 </span>
              {npc.conditions.map((c: any) => typeof c === 'string' ? c : c.name).filter(Boolean).join('、')}
            </p>
          )}
          <StatGrid npc={npc} />
          {npc.attributes && Object.keys(npc.attributes).length > 0 && (
            <div className="pt-1.5 border-t border-ink-200/70"><AttrGrid attrs={npc.attributes} /></div>
          )}
          {npc.skills && npc.skills.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">技能 </span>{npc.skills.map(textValue).join('、')}
            </p>
          )}
          {npc.traits && npc.traits.length > 0 && (
            <div className="pt-1.5 border-t border-ink-200/70">
              <p className="text-3xs font-bold text-ink-500">特性 / 动作</p>
              {npc.traits.map((t, i) => <p key={i} className="text-2xs text-ink-700">· {t}</p>)}
            </div>
          )}
          {npc.equipment && npc.equipment.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">装备 </span>{npc.equipment.join('、')}
            </p>
          )}
          {npc.related_locations && npc.related_locations.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联地点 </span>{npc.related_locations.join('、')}
            </p>
          )}
          {npc.related_npcs && npc.related_npcs.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联角色 </span>{npc.related_npcs.join('、')}
            </p>
          )}
          {npc.related_creatures && npc.related_creatures.length > 0 && (
            <p className="text-2xs pt-1.5 border-t border-ink-200/70">
              <span className="font-bold text-ink-500">关联生物 </span>{npc.related_creatures.join('、')}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-2 pt-2 border-t-2 border-parch-600/60 bg-parch-50 rounded-lg px-2.5 py-2">
          <p className="text-center font-bold text-ink-900 text-sm">{npc.name}</p>
          <p className="text-center text-2xs text-ink-500 italic mt-0.5">
            {npc.role || '未知身份'}
            {npc.race && npc.race !== '???' ? ` · ${npc.race}` : ''} · {npc.alive === false ? '已故' : CAT_LABELS[cat]}
          </p>
          <div className="paper-rule my-2" />
          <div className="flex justify-between gap-2 text-2xs">
            <span><b className="text-ink-500 font-medium">护甲等级</b> <b className="font-mono">{npc.ac}</b></span>
            <span><b className="text-ink-500 font-medium">生命值</b> <b className="font-mono">{npc.hp}/{npc.max_hp}</b></span>
            <span><b className="text-ink-500 font-medium">等级</b> <b className="font-mono">{npc.level}</b></span>
          </div>
          {npc.location && <p className="text-2xs text-ink-500 mt-1">位置：{npc.location}</p>}
          {npc.conditions && npc.conditions.length > 0 && (
            <p className="text-2xs mt-1">
              <span className="font-bold text-ink-500">状态 </span>
              {npc.conditions.map((c: any) => typeof c === 'string' ? c : c.name).filter(Boolean).join('、')}
            </p>
          )}
          {npc.attributes && Object.keys(npc.attributes).length > 0 && (
            <><div className="paper-rule my-2" /><AttrGrid attrs={npc.attributes} size="lg" /></>
          )}
          {npc.skills && npc.skills.length > 0 && (
            <><div className="paper-rule my-2" /><p className="text-2xs"><span className="font-bold text-ink-500">技能 </span>{npc.skills.map(textValue).join('、')}</p></>
          )}
          {npc.traits && npc.traits.length > 0 && (
            <><div className="paper-rule my-2" /><p className="text-3xs font-bold text-ink-500">特性 / 动作</p>
              {npc.traits.map((t, i) => <p key={i} className="text-2xs text-ink-700">· {t}</p>)}</>
          )}
          {npc.equipment && npc.equipment.length > 0 && (
            <><div className="paper-rule my-2" /><p className="text-2xs"><span className="font-bold text-ink-500">装备 </span>{npc.equipment.join('、')}</p></>
          )}
          {(npc.related_locations?.length || npc.related_npcs?.length || npc.related_creatures?.length) ? (
            <>
              <div className="paper-rule my-2" />
              {npc.related_locations && npc.related_locations.length > 0 && <p className="text-2xs"><span className="font-bold text-ink-500">关联地点 </span>{npc.related_locations.join('、')}</p>}
              {npc.related_npcs && npc.related_npcs.length > 0 && <p className="text-2xs"><span className="font-bold text-ink-500">关联角色 </span>{npc.related_npcs.join('、')}</p>}
              {npc.related_creatures && npc.related_creatures.length > 0 && <p className="text-2xs"><span className="font-bold text-ink-500">关联生物 </span>{npc.related_creatures.join('、')}</p>}
            </>
          ) : null}
          <div className="paper-rule my-2" />
          <Row k="外貌" v={npc.appearance} />
          <Row k="性格" v={npc.personality} c="text-brand-600" />
          <Row k="动机" v={npc.motivation} c="text-amber-700" />
          <Row k="秘密" v={npc.secret} c="text-red-700" />
          <Row k="关联" v={npc.relation_to_plot} c="text-sky-700" />
        </div>
      )}
    </details>
  );
}
