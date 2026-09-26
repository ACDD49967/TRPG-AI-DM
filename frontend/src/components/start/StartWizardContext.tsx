/**
 * 开始向导的共享上下文。
 *
 * 四个步骤组件原先各收 68-84 个 props（整包展开），根因是状态全堆在 StartScreen。
 * 现在状态都在各自的 hook 里，StartScreen 把它们的返回值与本页局部状态聚合一次，
 * 步骤组件用 `useStartWizard()` 取用——既不用逐层透传，也便于后续按区块拆子组件。
 *
 * 类型直接取各 hook 的 `ReturnType` 的交集：不做第二套声明，hook 改了什么这里就跟着变，
 * 缺字段会在 `satisfies` 处直接报错（此前用 `[key: string]: any` 的宽松接口会把它吞掉）。
 */
import { createContext, useContext, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import type { useModelSettings } from './useModelSettings';
import type { useKnowledgeActions } from './useKnowledgeActions';
import type { useMediaActions } from './useMediaActions';
import type { useSaveActions } from './useSaveActions';
import type { useCharacterCardActions } from './useCharacterCardActions';
import type { useCharacterDraft } from './useCharacterDraft';
import type { useScenarioStudio } from './useScenarioStudio';
import type { GameSystem } from '../../gameSystems';

/** 仍留在 StartScreen 的页面级状态与回调 */
export interface StartWizardLocal {
  step: number;
  setStep: Dispatch<SetStateAction<number>>;
  scenarioMode: 'existing' | 'split' | 'generate';
  setScenarioMode: (v: 'existing' | 'split' | 'generate') => void;
  username: string;
  setUsername: (v: string) => void;
  playMode: 'lite' | 'deep';
  setPlayMode: (v: 'lite' | 'deep') => void;
  gameSystem: GameSystem;
  setGameSystem: (v: GameSystem) => void;
  showRulebook: boolean;
  setShowRulebook: (v: boolean) => void;
  loading: boolean;
  error: string;
  setError: (v: string) => void;
  start: () => Promise<void>;
  callAI: (backstoryOnly: boolean) => Promise<void>;
  authUsername?: string;
  onLogout?: () => void;
  setSaves: Dispatch<SetStateAction<StartWizardLocal['saves']>>;
  setSaveLabel: Dispatch<SetStateAction<string>>;
  setCharCards: Dispatch<SetStateAction<StartWizardLocal['charCards']>>;
  setCharCardName: Dispatch<SetStateAction<string>>;
  saves: Array<{ id: string; label: string; auto: boolean; session_id: string; created_at: string; character_name: string; game_system: string }>;
  saveLabel: string;
  charCards: Array<{ id: string; name: string; character_name: string; game_system: string; race: string; char_class: string; created_at: string; updated_at: string }>;
  charCardName: string;
}

export type StartWizardValue =
  ReturnType<typeof useModelSettings> &
  ReturnType<typeof useKnowledgeActions> &
  ReturnType<typeof useMediaActions> &
  ReturnType<typeof useSaveActions> &
  ReturnType<typeof useCharacterCardActions> &
  ReturnType<typeof useCharacterDraft> &
  ReturnType<typeof useScenarioStudio> &
  StartWizardLocal;

const StartWizardContext = createContext<StartWizardValue | null>(null);

export function StartWizardProvider({ value, children }: {
  value: StartWizardValue; children: ReactNode;
}) {
  return <StartWizardContext.Provider value={value}>{children}</StartWizardContext.Provider>;
}

export function useStartWizard(): StartWizardValue {
  const value = useContext(StartWizardContext);
  if (!value) throw new Error('useStartWizard 必须在 StartWizardProvider 内使用');
  return value;
}
