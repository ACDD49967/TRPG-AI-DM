/**
 * 可选向量模型的下载流：BGE-M3 / BGE-Reranker 与小模型共用同一段 SSE 风格读取。
 *
 * 从 `useModelSettings` 拆出；状态仍由调用方持有，这里只负责发请求、解析事件与写入进度。
 */
import { useCallback } from 'react';

type VectorMode = 'local' | 'bge';

export interface ModelDownloadDeps {
  setBgeBusy: (v: 'embedding' | 'reranker' | null) => void;
  setBgeStatus: (v: string) => void;
  setBgeProgress: (v: number | null) => void;
  setBgeDownloaded: (v: boolean) => void;
  setBgeRerankerDownloaded: (v: boolean) => void;
  setSmallBusy: (v: boolean) => void;
  setSmallStatus: (v: string) => void;
  setSmallProgress: (v: number | null) => void;
  setSmallDownloaded: (v: boolean) => void;
  setSmallDeclined: (v: boolean) => void;
  setVectorModeNow: (mode: VectorMode) => void;
}

export function useModelDownloads(deps: ModelDownloadDeps) {
  const {
    setBgeBusy, setBgeStatus, setBgeProgress, setBgeDownloaded, setBgeRerankerDownloaded,
    setSmallBusy, setSmallStatus, setSmallProgress, setSmallDownloaded, setSmallDeclined,
    setVectorModeNow,
  } = deps;

  /** 读一条 SSE 风格流（download-bge / download-small 共用），逐条回调事件。 */
  const readEventStream = useCallback(async (
    response: Response, onEvent: (data: Record<string, any>) => void,
  ) => {
    if (!response.ok || !response.body) {
      const e = await response.json().catch(() => ({}));
      throw new Error(e.detail || '下载失败');
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() || '';
      for (const evt of events) {
        const line = evt.split('\n').find(l => l.startsWith('data: '));
        if (!line) continue;
        onEvent(JSON.parse(line.slice(6)));
      }
    }
  }, []);

  const downloadBge = useCallback(async (kind: 'embedding' | 'reranker') => {
    setBgeBusy(kind); setBgeStatus(''); setBgeProgress(null);
    try {
      const r = await fetch('/api/models/download-bge/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind }),
      });
      await readEventStream(r, (data) => {
        if (data.type === 'status') setBgeStatus(data.msg || '');
        else if (data.type === 'progress') {
          if (typeof data.percent === 'number') setBgeProgress(data.percent);
        } else if (data.type === 'complete') {
          setBgeStatus(`${kind === 'embedding' ? 'BGE-M3' : 'BGE-Reranker-base'} 下载完成`);
          if (kind === 'embedding') { setBgeDownloaded(true); setVectorModeNow('bge'); }
          if (kind === 'reranker') setBgeRerankerDownloaded(true);
        } else if (data.type === 'error') {
          throw new Error(data.msg || '下载失败');
        }
      });
    } catch (e: unknown) {
      setBgeStatus(`下载失败：${e instanceof Error ? e.message : '未知错误'}`);
    } finally {
      setBgeBusy(null); setBgeProgress(null);
    }
  }, [readEventStream, setBgeBusy, setBgeStatus, setBgeProgress, setBgeDownloaded,
      setBgeRerankerDownloaded, setVectorModeNow]);

  const downloadSmall = useCallback(async () => {
    setSmallBusy(true); setSmallStatus(''); setSmallProgress(null);
    try {
      const r = await fetch('/api/models/download-small/stream', { method: 'POST' });
      await readEventStream(r, (data) => {
        if (data.type === 'status') setSmallStatus(data.msg || '');
        else if (data.type === 'progress') {
          if (typeof data.percent === 'number') setSmallProgress(data.percent);
        } else if (data.type === 'complete') {
          setSmallStatus('基底模型下载完成');
          setSmallDownloaded(true);
          setSmallDeclined(false);
        } else if (data.type === 'error') {
          throw new Error(data.msg || '下载失败');
        }
      });
    } catch (e: unknown) {
      setSmallStatus(`下载失败：${e instanceof Error ? e.message : '未知错误'}`);
    } finally {
      setSmallBusy(false); setSmallProgress(null);
    }
  }, [readEventStream, setSmallBusy, setSmallStatus, setSmallProgress, setSmallDownloaded,
      setSmallDeclined]);

  return { downloadBge, downloadSmall };
}
