/** 扩展包动作：列表加载、新增、AI 生成与删除。 */
export interface ExtActionsContext {
  username: string;
  apiKey: string;
  baseUrl: string;
  modelName: string;
  extName: string;
  extDesc: string;
  extContent: string;
  extSystem: string;
  extTags: string;
  extGenDesc: string;
  setExtList: (v: any) => void;
  setExtName: (v: any) => void;
  setExtDesc: (v: any) => void;
  setExtContent: (v: any) => void;
  setExtTags: (v: any) => void;
  setExtGenDesc: (v: any) => void;
  setExtBusy: (v: any) => void;
  setExtErr: (v: any) => void;
  setActiveExtIds: (v: any) => void;
}

export function createExtActions(ctx: ExtActionsContext) {
  const loadExts = async () => {
    try {
      const r = await fetch(`/api/extensions?username=${encodeURIComponent(ctx.username || 'default')}`);
      if (r.ok) ctx.setExtList((await r.json()).extensions || []);
    } catch { /* 扩展包不可用不影响其它步骤 */ }
  };

  const addExt = async () => {
    ctx.setExtBusy(true); ctx.setExtErr('');
    try {
      const r = await fetch('/api/extensions', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: ctx.username || 'default',
          name: ctx.extName || '未命名扩展包',
          description: ctx.extDesc,
          content: ctx.extContent,
          system: ctx.extSystem,
          tags: ctx.extTags.split(',').map((s: any) => s.trim()).filter(Boolean),
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '添加失败');
      }
      ctx.setExtName(''); ctx.setExtDesc(''); ctx.setExtContent(''); ctx.setExtTags('');
      await loadExts();
    } catch (e: unknown) {
      ctx.setExtErr(e instanceof Error ? e.message : '添加失败');
    } finally {
      ctx.setExtBusy(false);
    }
  };

  const genExt = async () => {
    ctx.setExtBusy(true); ctx.setExtErr('');
    try {
      const r = await fetch('/api/extensions/generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: ctx.username || 'default', description: ctx.extGenDesc, system: ctx.extSystem,
          api_key: ctx.apiKey || undefined, model_name: ctx.modelName || undefined, base_url: ctx.baseUrl || undefined,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '生成失败');
      }
      ctx.setExtGenDesc('');
      await loadExts();
    } catch (e: unknown) {
      ctx.setExtErr(e instanceof Error ? e.message : '生成失败');
    } finally {
      ctx.setExtBusy(false);
    }
  };

  const deleteExt = async (id: string) => {
    try {
      await fetch(`/api/extensions/${id}?username=${encodeURIComponent(ctx.username || 'default')}`, { method: 'DELETE' });
      ctx.setActiveExtIds((ids: any[]) => ids.filter((x: any) => x !== id));
      await loadExts();
    } catch { /* 删除失败保持列表现状 */ }
  };

  return { loadExts, addExt, genExt, deleteExt };
}
