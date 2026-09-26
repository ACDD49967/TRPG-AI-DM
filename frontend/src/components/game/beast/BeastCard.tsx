/** 生物条目卡片：折叠头 + 数值面板 + 行内编辑 + 关联地点。
 *
 * 从 `BeastModal.tsx` 拆出；数值读取用同一套 `get(中文, 英文, 小写)` 回退顺序。
 */
import InlineEdit from '../../ui/InlineEdit';
import { textValue } from '../../../utils/textValue';
import { crToXp, translateMonsterDesc } from '../monsterFormat';
import BeastStatBlocks from './BeastStatBlocks';
import { deleteMediaItem } from '../mediaActions/deleteMedia';


export default function BeastCard({ b, scopedMaps, q, status, setBestiary }: {
  b: any;
  scopedMaps: any[];
  q: (text: any) => string;
  status: any;
  setBestiary: (updater: any) => void;
}) {
                    const relatedMaps = scopedMaps.filter((m: any) => q(`${b.details?.habitat||''} ${b.description} ${b.details?.lore||''}`).includes(q(m.name)) || q(m.description).includes(q(b.name)));
                    const s = b.stats || {};
                    const get = (...keys: string[]) => {
                      const raw = keys.map((k: any) =>s[k]).find((v: any) =>v!==undefined && v!=='');
                      return raw === undefined ? '—' : textValue(raw);
                    };
                    const abilities: Array<[string,string]> = [
                      ['力量', get('力量','STR','str')], ['敏捷', get('敏捷','DEX','dex')],
                      ['体质', get('体质','CON','con')], ['智力', get('智力','INT','int')],
                      ['感知', get('感知','WIS','wis')], ['魅力', get('魅力','CHA','cha')],
                    ];
                    const baseSaves = abilities.map(([k, v]) => {
                      const n = Number(v);
                      return [k, Number.isFinite(n) && v !== '—' ? (Math.floor((n - 10) / 2) >= 0 ? `+${Math.floor((n - 10) / 2)}` : `${Math.floor((n - 10) / 2)}`) : '—'] as [string, string];
                    });
                    const skills = get('技能','Skills','skills');
                    const saves = get('豁免','Saves','saves');
                    const senses = get('感官','Senses','senses');
                    const languages = get('语言','Languages','languages');
                    const challenge = get('挑战等级','挑战','CR','cr');
                    const xp = crToXp(challenge);
                    const dexStat = Number(get('敏捷','DEX','dex'));
                    const initiative = Number.isFinite(dexStat) && dexStat !== 0 ? `${Math.floor((dexStat - 10) / 2) >= 0 ? '+' : ''}${Math.floor((dexStat - 10) / 2)}` : '—';
                    const traits = get('特性','Traits','traits');
                    const actions = get('动作','Actions','actions');
  return (
                      <details key={b.id} className="group entry-card p-3 mb-3">
                        <summary className="cursor-pointer select-none list-none">
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2 min-w-0">
                              {b.image_path && <img src={b.image_path} alt="" loading="lazy" decoding="async" onError={(e: any) =>{e.currentTarget.style.display='none';}} className="w-9 h-9 object-cover rounded border border-amber-900/20 shrink-0" />}
                              <span className="paper-title text-base font-bold text-ink-900 truncate">{b.name}</span>
                              <span className={`scope-badge ${b.scenario_id ? 'scope-badge-scenario' : 'scope-badge-global'}`}>{b.scenario_id ? '当前剧本' : '通用参考'}</span>
                            </div>
                            <span className="text-[9px] text-ink-400 shrink-0">{challenge!=='—'?`CR ${challenge}${xp!=='—'?`（XP ${xp}）`:''} · `:''}HP {get('HP','hp','生命')} · AC {get('AC','ac','护甲')}<span className="ml-1 group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span></span>
                          </div>
                        </summary>
                        <div className="mt-2">
                        <div className="flex justify-end mb-1">
                          <InlineEdit
                            label="编辑生物"
                            fields={[
                              { key: 'name', label: '名称', value: b.name || '' },
                              { key: 'description', label: '描述', value: b.description || '', type: 'textarea' },
                              { key: 'hp', label: 'HP', value: String(b.stats?.HP ?? b.stats?.hp ?? '') },
                              { key: 'ac', label: 'AC', value: String(b.stats?.AC ?? b.stats?.ac ?? '') },
                            ]}
                            onSave={async (values) => {
                              const u = (status?.username as string) || 'default';
                              const response = await fetch(
                                `/api/bestiary/${encodeURIComponent(b.id)}?username=${encodeURIComponent(u)}`,
                                {
                                  method: 'PUT',
                                  headers: { 'Content-Type': 'application/json' },
                                  body: JSON.stringify({
                                    name: values.name,
                                    description: values.description,
                                    stats: { ...(b.stats || {}), HP: values.hp, AC: values.ac },
                                  }),
                                });
                              if (!response.ok) return;
                              const body = await response.json();
                              setBestiary((prev: any[]) => prev.map((item) =>
                                item.id === b.id ? { ...item, ...(body.beast || {}) } : item));
                            }}
                          >
                            <span className="text-[10px] text-ink-500">编辑名称 / 描述 / 数值</span>
                          </InlineEdit>
                          <button
                            type="button"
                            className="text-[10px] text-red-600 hover:text-red-700 ml-2 shrink-0 px-1.5 min-h-[28px]"
                            onClick={async () => {
                              if (!window.confirm(`确定删除生物「${b.name}」？此操作不可恢复。`)) return;
                              if (await deleteMediaItem('beast', b.id, status?.username)) {
                                setBestiary((prev: any[]) => prev.filter((item) => item.id !== b.id));
                              }
                            }}
                          >
                            删除
                          </button>
                        </div>
                        {b.image_path && (
                          <a href={b.image_path} target="_blank" rel="noreferrer" title="查看原图" className="block mb-3">
                            <img src={b.image_path} alt={b.name} loading="lazy" decoding="async" onError={(e: any) =>{e.currentTarget.style.display='none';}} className="w-full max-h-72 object-contain bg-gray-100 rounded-lg border border-amber-900/20" />
                          </a>
                        )}
                        <div className="flex items-start gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-[10px] text-ink-500 italic">
                              {b.scenario_id ? <span className="text-emerald-700 font-medium">当前剧本</span> : <span className="text-ink-400 font-medium">通用参考</span>}
                              {' · '}{b.system}{b.tags&&b.tags.length>0?` · ${b.tags.join('、')}`:''}
                            </p>
                            <div className="grid grid-cols-3 gap-1 mt-1.5 text-[10px]">
                              <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">AC</span> <b>{get('AC','ac','护甲')}</b></div>
                              <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">HP</span> <b>{get('HP','hp','生命')}</b></div>
                              <div className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5"><span className="text-ink-500">速度</span> <b>{get('速度','Speed','speed')}</b></div>
                            </div>
                          </div>
                        </div>

                        <BeastStatBlocks
                          b={b}
                          get={get}
                          abilities={abilities}
                          baseSaves={baseSaves}
                          skills={skills}
                          saves={saves}
                          senses={senses}
                          languages={languages}
                          challenge={challenge}
                          xp={xp}
                          initiative={initiative}
                        />

                        {/* 描述 / 特性 / 动作 */}
                        {(b.description_zh || b.description)&&<p className="mt-2 text-[10px] text-ink-600 italic leading-relaxed">{(b.description_zh || b.description)}{b.description_zh && b.description ? <span className="text-ink-400">（原文：{translateMonsterDesc(b.description).slice(0,60)}...）</span> : null}</p>}
                        {(traits!=='—'||actions!=='—') && (
                          <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-1 text-[10px] text-ink-700">
                            {traits!=='—'&&<p><span className="text-ink-500 font-medium">特性：</span>{traits}</p>}
                            {actions!=='—'&&<p><span className="text-ink-500 font-medium">动作：</span>{actions}</p>}
                          </div>
                        )}
                        {b.details && (
                          <div className="mt-2 border-t border-amber-900/10 pt-1.5 space-y-0.5 text-[10px] text-ink-600">
                            {b.details.habits&&<p>习性：{b.details.habits}</p>}
                            {b.details.habitat&&<p>栖息地：{b.details.habitat}</p>}
                            {b.details.lore&&<p>传说：{b.details.lore}</p>}
                          </div>
                        )}
                        {relatedMaps.length>0 && (
                          <div className="mt-2 pt-1.5 border-t border-amber-900/10">
                            <p className="text-[9px] text-ink-400 mb-0.5">关联地点</p>
                            <div className="flex flex-wrap gap-1">{relatedMaps.map((m: any) =><span key={m.id} className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-1.5 py-0.5">{m.name}</span>)}</div>
                          </div>
                        )}
                        </div>
                      </details>
  );
}
