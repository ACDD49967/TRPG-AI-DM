/** 法术图鉴弹窗：筛选、通用参考、自建法术、SRD 翻译。
 *
 * 从 GameScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */
import Modal from '../ui/Modal';
import ProgressBar from '../ui/ProgressBar';
import EmptyState from '../ui/EmptyState';
import SpellBuilderForm from './spell/SpellBuilderForm';
import SpellEntryCard from './spell/SpellEntryCard';

export interface SpellModalProps {
  [key: string]: any;
}

export default function SpellModal(props: SpellModalProps) {
  const {
    addDmSpell,
    currentSid,
    dmSpell,
    scenarioSpells,
    scopedSpells,
    setDmSpell,
    setShowGlobalRefSpells,
    setShowSpellBuilder,
    setShowSpells,
    setSpellQuery,
    setSpells,
    showGlobalRefSpells,
    showSpellBuilder,
    showSpells,
    spellQuery,
    srdProgress,
    srdTranslating,
    status,
    translateSrd,
  } = props;

  return (
    <>
          <Modal
            open={showSpells}
            onClose={() => setShowSpells(false)}
            paper
            size="lg"
            icon="✨"
            title="法术 / 仪式"
            subtitle={currentSid ? '默认仅显示当前剧本条目；可切换显示通用参考' : '通用法术库（所有剧本可用）'}
            headExtra={
              <>
                <button onClick={()=>setShowSpellBuilder((v: any) =>!v)} className="btn-xs-paper">
                  {showSpellBuilder ? '收起自建' : '自建法术'}
                </button>
                <button onClick={translateSrd} disabled={srdTranslating} className="btn-xs-brand">
                  {srdTranslating ? '机翻中...' : '翻译 SRD'}
                </button>
                {currentSid && (
                  <button onClick={()=>setShowGlobalRefSpells((v: any) =>!v)} className={`btn-xs ${showGlobalRefSpells ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                    {showGlobalRefSpells ? '仅当前剧本' : '通用参考'}
                  </button>
                )}
              </>
            }
          >
                {srdProgress && (
                  <ProgressBar className="mb-3" label="批量机翻 SRD 法术" value={srdProgress.done} max={srdProgress.total} />
                )}
                <input value={spellQuery} onChange={(e: any) =>setSpellQuery(e.target.value)} placeholder="搜索法术 / 仪式…" className="input-field text-xs mb-3 !py-2" aria-label="搜索法术" />
                {showSpellBuilder && (
                  <SpellBuilderForm
                    dmSpell={dmSpell}
                    setDmSpell={setDmSpell}
                    onSave={() => { addDmSpell(); setShowSpellBuilder(false); }}
                  />
                )}
                {scopedSpells.filter((s: any) =>!spellQuery || `${s.name_zh||s.name} ${s.school} ${s.level} ${s.description_zh||s.description} ${s.description}`.toLowerCase().includes(spellQuery.toLowerCase())).length===0 && (
                  <EmptyState
                    icon="✨"
                    title="没有找到法术"
                    hint={currentSid && !showGlobalRefSpells && scenarioSpells.length===0 ? '当前剧本暂无法术图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入法术图鉴 / 自建法术'}
                  />
                )}
                {scopedSpells.filter((s: any) =>!spellQuery || `${s.name_zh||s.name} ${s.school} ${s.level} ${s.description_zh||s.description} ${s.description}`.toLowerCase().includes(spellQuery.toLowerCase())).map((s: any) =>(
                  <SpellEntryCard key={s.id} s={s} status={status} setSpells={setSpells} />
                ))}
          </Modal>
    </>
  );
}
