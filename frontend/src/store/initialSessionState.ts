/** 会话默认值：初始角色状态、初始场景，以及 reset/goToStart 共用的干净会话字段。
 *
 * 从 `gameStateShape` 拆出：这些是"新会话长什么样"的数据，
 * 与 GameState 的字段契约分开存放。
 */
import type { CharacterStatus, SceneInfo } from './gameTypes';

export const initialStatus: CharacterStatus = {
  hp: 30,
  maxHp: 30,
  mp: 10,
  maxMp: 10,
  xp: 0,
  gold: 10,
  level: 1,
  ac: 10,
  inventory: [],
  attributes: { str: 12, dex: 12, con: 12, int: 12, wis: 12, cha: 12 },
  scenario_id: '',
};

export const initialScene: SceneInfo = {
  location: '冒险的起点',
  time: '第1天',
  weather: '',
  npcs_here: [],
  light: '',
  light_source: '',
};

/** reset() 与 goToStart() 共用的干净会话字段（不含 screen / sessionId）。 */
export function freshSessionFields() {
  return {
    narrative: [],
    currentTokenBuffer: '',
    narrativeId: 0,
    status: { ...initialStatus },
    choices: [],
    isProcessing: false,
    latestDiceRoll: null,
    combat: null,
    initiative: null,
    placements: [],
    combatLog: [],
    journalStatus: 'idle' as const,
    worldOutline: null,
    decisionSuggestions: [],
    journalData: null,
    mediaVersion: 0,
    sceneInfo: { ...initialScene },
    metrics: null,
    pendingLevelUp: null,
  };
}
