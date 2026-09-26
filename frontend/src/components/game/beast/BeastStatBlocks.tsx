/** 生物数值面板：按系统显示 4e / CoC / 六维与标准字段。 */
export default function BeastStatBlocks({
  b, get, abilities, baseSaves, skills, saves, senses, languages,
  challenge, xp, initiative,
}: {
  b: any;
  get: (...keys: string[]) => string;
  abilities: Array<[string, string]>;
  baseSaves: Array<[string, string]>;
  skills: string;
  saves: string;
  senses: string;
  languages: string;
  challenge: string;
  xp: string;
  initiative: string;
}) {
  return (
    <>
      {/* D&D4e 关键数值 */}
      {b.system === 'dnd4e' && (
        <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2 text-[10px]">
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">强韧</span> <b>{get('强韧', 'Fortitude', 'fort')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">反射</span> <b>{get('反射', 'Reflex', 'ref')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">意志</span> <b>{get('意志', 'Will', 'will')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">等级</span> <b>{get('等级', 'Level', 'level')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">XP</span> <b>{get('XP', 'xp')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-ink-400">角色</span> <b>{get('角色类型', 'role')}</b></div>
        </div>
      )}

      {/* 六维 / COC 关键数值 */}
      {b.system === 'coc' ? (
        <div className="grid grid-cols-2 gap-1 mt-2 border-t border-amber-900/10 pt-2">
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">HP</span> <b className="text-xs">{get('HP', 'hp', '生命')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">MP</span> <b className="text-xs">{get('MP', 'mp', '魔法')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">伤害加值</span> <b className="text-xs">{get('伤害加值', 'DB', 'damage_bonus')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5"><span className="text-[8px] text-ink-400">护甲</span> <b className="text-xs">{get('护甲', '装甲', 'armor')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-ink-400">技能</span> <b className="text-xs">{get('技能', 'Skills', 'skills')}</b></div>
          <div className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 col-span-2"><span className="text-[8px] text-ink-400">理智损失</span> <b className="text-xs">{get('理智损失', 'SAN Loss', 'sanity')}</b></div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-1 mt-2 border-t border-amber-900/10 pt-2">
            {abilities.map(([k, v]) => (
              <div key={k} className="bg-white border border-amber-900/10 rounded px-1.5 py-0.5 text-center">
                <span className="text-[8px] text-ink-400 font-semibold">{k}</span>
                <div className="text-xs font-bold">{v}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-6 gap-1 mt-1.5">
            {baseSaves.map(([k, v]) => (
              <div key={k} className="bg-white border border-amber-900/10 rounded px-1 py-0.5 text-center">
                <span className="text-[7px] text-ink-400">{k}</span>
                <div className="text-[10px] font-bold">{v}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 标准字段 */}
      {(skills !== '—' || senses !== '—' || languages !== '—' || challenge !== '—' || xp !== '—' || initiative !== '—' || saves !== '—') && (
        <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-ink-700">
          {initiative !== '—' && <p><span className="text-ink-500 font-medium">先攻：</span>{initiative}</p>}
          {saves !== '—' && <p><span className="text-ink-500 font-medium">豁免：</span>{saves}</p>}
          {skills !== '—' && <p><span className="text-ink-500 font-medium">技能：</span>{skills}</p>}
          {senses !== '—' && <p><span className="text-ink-500 font-medium">感官：</span>{senses}</p>}
          {languages !== '—' && <p><span className="text-ink-500 font-medium">语言：</span>{languages}</p>}
          {challenge !== '—' && <p><span className="text-ink-500 font-medium">挑战等级：</span>{challenge} {xp !== '—' ? `（XP ${xp}）` : ''}</p>}
        </div>
      )}
    </>
  );
}
