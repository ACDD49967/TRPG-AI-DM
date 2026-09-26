/** 知识库动作的共享上下文（状态与 setter 由 useKnowledgeActions 提供）。 */
import type { MutableRefObject } from 'react';

export interface KbActionsContext {
  username: string;
  apiKey: string;
  baseUrl: string;
  modelName: string;
  scenarioId: string;
  splitter: 'semantic' | 'llm' | 'recursive';
  kbTitle: string;
  kbContent: string;
  kbSystem: string;
  kbTags: string;
  setKbDocs: (v: any) => void;
  setKbTitle: (v: any) => void;
  setKbContent: (v: any) => void;
  setKbTags: (v: any) => void;
  setKbBusy: (v: any) => void;
  setKbLlmBusy: (v: any) => void;
  setKbErr: (v: any) => void;
  setKbUploadFile: (v: any) => void;
  setKbProgress: (v: any) => void;
  kbEsRef: MutableRefObject<EventSource | null>;
  kbStopRef: MutableRefObject<(() => void) | null>;
  kbTaskIdRef: MutableRefObject<string>;
}
