/** 知识库摄入动作：文字备注、文件上传（带 SSE 进度）、取消。
 *
 * 从 `kbActions` 拆出——这块是"往知识库里写"，与列表/删除/播种等查询动作分开。
 */
import type { KbActionsContext } from './kbContext';

export function createKbIngest(ctx: KbActionsContext, loadKb: () => Promise<void>) {
  const addKbNote = async () => {
    ctx.setKbBusy(true); ctx.setKbErr('');
    try {
      const r = await fetch('/api/knowledge', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: ctx.kbTitle || '未命名知识',
          content: ctx.kbContent,
          system: ctx.kbSystem,
          source: 'player-note',
          tags: ctx.kbTags.split(',').map((s: any) => s.trim()).filter(Boolean),
          username: ctx.username || 'default',
          splitter: ctx.splitter,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '添加失败');
      }
      ctx.setKbTitle(''); ctx.setKbContent(''); ctx.setKbTags('');
      await loadKb();
    } catch (e: unknown) {
      ctx.setKbErr(e instanceof Error ? e.message : '添加失败');
    } finally {
      ctx.setKbBusy(false);
    }
  };

  const uploadKb = async (file: File) => {
    ctx.setKbBusy(true); ctx.setKbErr(''); ctx.setKbProgress(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', ctx.kbTitle || file.name);
      fd.append('system', ctx.kbSystem);
      fd.append('source', 'upload');
      fd.append('tags', ctx.kbTags);
      fd.append('username', ctx.username || 'default');
      fd.append('splitter', ctx.splitter);
      const r = await fetch('/api/tasks/upload-document', { method: 'POST', body: fd });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '上传失败');
      }
      const d = await r.json() as { events_url: string; task_id?: string };
      ctx.kbTaskIdRef.current = d.task_id || '';
      await new Promise<void>((resolve, reject) => {
        let settled = false;
        const es = new EventSource(d.events_url);
        ctx.kbEsRef.current = es;
        const finish = (err?: Error) => {
          if (settled) return;
          settled = true;
          es.close();
          ctx.kbEsRef.current = null;
          ctx.kbStopRef.current = null;
          if (err) reject(err); else resolve();
        };
        ctx.kbStopRef.current = () => finish();
        es.onmessage = (ev: any) => {
          try {
            const t = JSON.parse(ev.data) as {
              phase: string; message: string; progress: number; current: number;
              total: number; status: string; error?: string;
            };
            ctx.setKbProgress({
              phase: t.phase, message: t.message, progress: t.progress,
              current: t.current, total: t.total,
            });
            if (t.status === 'completed') finish();
            else if (t.status === 'cancelled') { ctx.setKbErr('已取消'); finish(); }
            else if (t.status === 'failed') finish(new Error(t.error || '上传失败'));
          } catch { /* event type 与 data 分隔时忽略 */ }
        };
        es.onerror = () => finish(new Error('进度连接中断'));
      });
      ctx.setKbTitle(''); ctx.setKbTags(''); ctx.setKbUploadFile(null);
      await loadKb();
    } catch (e: unknown) {
      ctx.setKbErr(e instanceof Error ? e.message : '上传失败');
    } finally {
      ctx.kbEsRef.current = null;
      ctx.kbStopRef.current = null;
      ctx.kbTaskIdRef.current = '';
      ctx.setKbBusy(false); ctx.setKbProgress(null);
    }
  };

  const cancelKbUpload = async () => {
    const tid = ctx.kbTaskIdRef.current;
    if (tid) {
      try { await fetch(`/api/tasks/${tid}/cancel`, { method: 'POST' }); } catch { /* 忽略 */ }
    }
    ctx.kbStopRef.current?.();
    ctx.setKbBusy(false);
    ctx.setKbProgress(null);
    ctx.setKbErr('已取消');
  };

  return { addKbNote, uploadKb, cancelKbUpload };
}
