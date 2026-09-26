/**
 * 内容库的写入动作：新增 NPC / 地点 / 生物 / 法术，以及两处批量机翻。
 *
 * 依赖与动作类型在本文件（`UseMediaActionsDeps`），实现按域拆到
 * `mediaActions/writeActions` 与 `mediaActions/translateActions`；这里只做组合。
 */
export interface UseMediaActionsDeps {
  bestiary: any[];
  dmBeast: { name: string; description: string; ac: string; hp: string; speed: string; str: string; dex: string; con: string; int: string; wis: string; cha: string; tags: string; traits: string; skills: string; actions: string; habitat: string; habits: string; lore: string; weakness: string };
  dmBeastImage: File | null;
  dmMap: { name: string; description: string; type: string; status: string; culture: string; districts: string; notable_figures: string; dangers: string; secret: string; locationsText: string };
  dmMapImage: File | null;
  dmNpc: { name: string; role?: string; location?: string; hp?: number; ac?: number; level?: number };
  dmNpcImage: File | null;
  dmSpell: { name: string; description: string; level: string; school: string; casting_time: string; range: string; components: string; duration: string; classes: string; ritual: boolean };
  maps: any[];
  mediaTranslate: { kind: 'locations' | 'bestiary'; done: number; total: number } | null;
  spells: any[];
  srdTranslating: boolean;
  scopedMaps: any[];
  scopedBestiary: any[];
  gameSystem: string;
  scenarioId: string;
  sessionId: string;
  username: string;
  setDmBeast: (v: any) => void;
  setDmBeastImage: (v: any) => void;
  setDmMap: (v: any) => void;
  setDmMapImage: (v: any) => void;
  setDmNpc: (v: any) => void;
  setDmNpcImage: (v: any) => void;
  setDmSpell: (v: any) => void;
  setMediaTranslate: (v: any) => void;
  setSrdProgress: (v: any) => void;
  setSrdTranslating: (v: any) => void;
}

import { createTranslateActions } from './mediaActions/translateActions';
import { createWriteActions } from './mediaActions/writeActions';


export function useMediaLibraryActions(deps: UseMediaActionsDeps) {
  const write = createWriteActions(deps);
  const translate = createTranslateActions(deps);
  return { ...write, ...translate };
}
