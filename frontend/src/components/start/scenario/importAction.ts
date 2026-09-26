/** 剧本文件导入长动作：上传、流式进度、完成后的基线保存与知识库刷新。 */
import type { MutableRefObject } from 'react';
import type { GameSystem } from '../../../gameSystems';
import { readEventStream, refreshScenarioList } from '../scenarioStream';

export interface ImportContext {
  username: string;
  apiKey: string;
  modelName: string;
  baseUrl: string;
  thinkingStrength: string;
  worldTone: string;
  splitter: string;
  chunkSize: number;
  customRules: string;
  customClasses: string[];
  customSkills: string[];
  extraAttributes: Record<string, string>;
  abortRef: MutableRefObject<AbortController | null>;
  setBusy: (v: boolean) => void;
  setProgress: (v: number) => void;
  setStage: (v: string) => void;
  setLive: (updater: (prev: string) => string) => void;
  setImportError: (updater: (prev: string) => string) => void;
  setFileName: (v: string) => void;
  setOutline: (v: string) => void;
  setScore: (v: number | null) => void;
  setWorldStateJson: (v: string) => void;
  setScenarioId: (v: string) => void;
  setSummary: (v: string) => void;
  setScenarioSystem: (v: GameSystem) => void;
  setGameSystem: (v: GameSystem) => void;
  setSourceChunks: (v: string[]) => void;
  setSelectedScenario: (v: string) => void;
  setShowScenarioList: (v: boolean) => void;
  setSavedScenarios: (v: Array<Record<string, unknown>>) => void;
  updateScenario: (overrides: Record<string, unknown>, sid: string) => void;
  loadKb: () => void;
}

export async function importScenarioFile(ctx: ImportContext, file: File): Promise<void> {
  const ac = new AbortController();
  ctx.abortRef.current = ac;
  ctx.setBusy(true);
  ctx.setImportError(() => '');
  ctx.setFileName(file.name);
  ctx.setLive(() => '');
  ctx.setStage('');
  ctx.setProgress(2);
  try {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('username', ctx.username || 'default');
    fd.append('splitter', ctx.splitter);
    fd.append('chunk_size', String(ctx.chunkSize));
    fd.append('tone', ctx.worldTone);
    fd.append('system', 'auto');
    fd.append('custom_rules', ctx.customRules || '');
    fd.append('custom_classes', JSON.stringify(ctx.customClasses));
    fd.append('custom_skills', JSON.stringify(ctx.customSkills));
    fd.append('extra_attributes', JSON.stringify(ctx.extraAttributes));
    fd.append('api_key', ctx.apiKey || '');
    fd.append('model_name', ctx.modelName || '');
    fd.append('base_url', ctx.baseUrl || '');
    fd.append('thinking_strength', ctx.thinkingStrength);
    const r = await fetch('/api/scenarios/import', { method: 'POST', body: fd, signal: ac.signal });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.detail || '导入失败');
    }
    await readEventStream(r, (data) => {
      if (data.type === 'gen_token') {
        ctx.setLive((prev) => prev + String(data.token));
      } else if (data.type === 'progress') {
        ctx.setProgress(Math.min(99, Number(data.percent) || 0));
        ctx.setStage(String(data.detail || data.label || ''));
        const detail = String(data.detail || '');
        if (detail && /出错|错误|失败|警告/.test(detail)) {
          ctx.setImportError((prev) => (prev ? `${prev}\n${detail}` : detail));
        }
      } else if (data.type === 'complete') {
        ctx.setOutline(String(data.content));
        ctx.setScore(typeof data.score === 'number' ? data.score : null);
        ctx.setWorldStateJson(String(data.world_state_json || ''));
        ctx.setScenarioId(String(data.scenario_id));
        ctx.setSummary(String(data.summary || ''));
        if (data.system) {
          const sys = data.system as GameSystem;
          ctx.setScenarioSystem(sys);
          ctx.setGameSystem(sys);
        }
        ctx.setSourceChunks((data.source_chunks || []) as string[]);
        ctx.setSelectedScenario(String(data.scenario_id));
        ctx.setShowScenarioList(false);
        // 导入完成即自动保存一次（保证基线落库）
        if (data.scenario_id) {
          ctx.updateScenario({
            world_outline: data.content,
            summary: data.summary || '',
            custom_rules: ctx.customRules,
            custom_classes: ctx.customClasses,
            custom_skills: ctx.customSkills,
            extra_attributes: ctx.extraAttributes,
          }, String(data.scenario_id));
        }
        ctx.setProgress(100);
      } else if (data.type === 'error') {
        throw new Error(String(data.msg || '导入失败'));
      }
    });
    ctx.setSavedScenarios(await refreshScenarioList(ctx.username) as Array<Record<string, unknown>>);
    ctx.loadKb();
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      ctx.setImportError(() => '已取消');
    } else {
      ctx.setImportError(() => (e instanceof Error ? e.message : '导入失败'));
    }
  } finally {
    if (ctx.abortRef.current === ac) ctx.abortRef.current = null;
    window.setTimeout(() => { ctx.setProgress(0); ctx.setStage(''); }, 800);
    ctx.setBusy(false);
  }
}
