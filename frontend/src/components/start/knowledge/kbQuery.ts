/** 知识库查询与批量动作：列表加载、删除、播种、LLM 智能注入。
 *
 * 从 `kbActions` 拆出；写入类动作（备注/上传/取消）见 `kbIngest`。
 */
import type { KbActionsContext } from './kbContext';

export function createKbQuery(ctx: KbActionsContext) {
  const loadKb = async () => {
    try {
      const r = await fetch(`/api/knowledge?username=${encodeURIComponent(ctx.username || 'default')}`);
      if (r.ok) ctx.setKbDocs((await r.json()).documents || []);
    } catch { /* 知识库不可用不影响其它步骤 */ }
  };

  const deleteKb = async (id: string) => {
    try {
      await fetch(`/api/knowledge/${id}?username=${encodeURIComponent(ctx.username || 'default')}`, { method: 'DELETE' });
      await loadKb();
    } catch { /* 删除失败保持列表现状 */ }
  };

  const seedKb = async () => {
    ctx.setKbBusy(true);
    try {
      await fetch('/api/knowledge/seed', { method: 'POST' });
      await loadKb();
    } catch { /* 播种失败保持列表现状 */ }
    finally { ctx.setKbBusy(false); }
  };

  const llmProcessKb = async () => {
    if (!ctx.apiKey.trim()) { ctx.setKbErr('请先在 API 连接中填写 Key'); return; }
    ctx.setKbLlmBusy(true); ctx.setKbErr('');
    try {
      const r = await fetch('/api/knowledge/llm-process', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: ctx.username || 'default', scenario_id: ctx.scenarioId,
          api_key: ctx.apiKey, model_name: ctx.modelName, base_url: ctx.baseUrl,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || 'LLM 处理失败');
      }
      const d = await r.json();
      ctx.setKbErr(`LLM 智能注入完成：地点 ${d.locations || 0}、生物 ${d.creatures || 0}、法术 ${d.spells || 0}`);
      await loadKb();
    } catch (e: unknown) {
      ctx.setKbErr(e instanceof Error ? e.message : 'LLM 处理失败');
    } finally {
      ctx.setKbLlmBusy(false);
    }
  };

  return { loadKb, deleteKb, seedKb, llmProcessKb };
}
