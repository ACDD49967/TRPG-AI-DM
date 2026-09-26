/**
 * 开始向导的启动副作用：首屏数据加载、配置持久化、错误 Toast、存档页刷新。
 *
 * 这些 effect 原先直接堆在 StartScreen；抽成 hook 后页面只负责装配，
 * 且所有依赖都显式传入，避免再从页面作用域隐式取值。
 */
import { useEffect } from 'react';
import { saveConfig } from '../../data/dndData';

export type SaveRow = {
  id: string; label: string; auto: boolean; session_id: string;
  created_at: string; character_name: string; game_system: string;
};

export type CharCardRow = {
  id: string; name: string; character_name: string; game_system: string;
  race: string; char_class: string; created_at: string; updated_at: string;
};

type SavedScenarioRow = {
  id: string; title: string; description: string; tone: string;
  score: number; total_sessions: number;
};

type ClassicScenarioRow = {
  name: string; system: string; tone: string; summary: string;
  source: string; outline: string[];
};

export interface StartBootstrapDeps {
  username: string;
  step: number;
  apiKey: string;
  modelName: string;
  baseUrl: string;
  error: string;
  aiErr: string;
  mediaErr: string;
  kbErr: string;
  extErr: string;
  worldGenErr: string;
  importErr: string;
  setSaves: (v: SaveRow[] | ((prev: SaveRow[]) => SaveRow[])) => void;
  setCharCards: (v: CharCardRow[] | ((prev: CharCardRow[]) => CharCardRow[])) => void;
  setSavedScenarios: (v: SavedScenarioRow[] | ((prev: SavedScenarioRow[]) => SavedScenarioRow[])) => void;
  setClassicScenarios: (v: ClassicScenarioRow[] | ((prev: ClassicScenarioRow[]) => ClassicScenarioRow[])) => void;
  showToast: (message: string, type: 'error') => void;
}

const userQuery = (username: string) => encodeURIComponent(username || 'default');

export function useStartBootstrap(deps: StartBootstrapDeps) {
  const {
    username, step, apiKey, modelName, baseUrl,
    error, aiErr, mediaErr, kbErr, extErr, worldGenErr, importErr,
    setSaves, setCharCards, setSavedScenarios, setClassicScenarios, showToast,
  } = deps;

  // 自动加载已保存剧本、经典剧本、存档与角色卡
  useEffect(() => {
    fetch(`/api/scenarios?username=${userQuery(username)}`).then(r => r.json())
      .then(d => setSavedScenarios(d.scenarios || [])).catch(() => {});
    fetch('/api/classic-scenarios').then(r => r.json())
      .then(d => setClassicScenarios(d.scenarios || [])).catch(() => {});
    fetch(`/api/saves?username=${userQuery(username)}`).then(r => r.json())
      .then(d => setSaves(d.saves || [])).catch(() => {});
    fetch(`/api/characters?username=${userQuery(username)}`).then(r => r.json())
      .then(d => setCharCards(d.cards || [])).catch(() => {});
  }, [username, setSavedScenarios, setClassicScenarios, setSaves, setCharCards]);

  // 自动保持配置（每次关键字段变化）
  useEffect(() => {
    saveConfig({ apiKey, modelName, baseUrl, username });
  }, [apiKey, modelName, baseUrl, username]);

  // 统一 Toast 通知
  useEffect(() => { if (error) showToast(error, 'error'); }, [error, showToast]);
  useEffect(() => { if (aiErr) showToast(aiErr, 'error'); }, [aiErr, showToast]);
  useEffect(() => { if (mediaErr) showToast(mediaErr, 'error'); }, [mediaErr, showToast]);
  useEffect(() => { if (kbErr) showToast(kbErr, 'error'); }, [kbErr, showToast]);
  useEffect(() => { if (extErr) showToast(extErr, 'error'); }, [extErr, showToast]);
  useEffect(() => { if (worldGenErr) showToast(worldGenErr, 'error'); }, [worldGenErr, showToast]);
  useEffect(() => { if (importErr) showToast(importErr, 'error'); }, [importErr, showToast]);

  // 进入存档页时刷新存档列表，避免显示已删除/过期存档
  useEffect(() => {
    if (step === 5) {
      fetch(`/api/saves?username=${userQuery(username)}`).then(r => r.json())
        .then(d => setSaves(d.saves || [])).catch(() => {});
    }
  }, [step, username, setSaves]);
}
