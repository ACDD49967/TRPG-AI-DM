/** 内容库写入门面：组合 NPC/法术、地点、生物三个动作工厂。 */
import type { UseMediaActionsDeps } from '../useMediaLibraryActions';
import { createBeastWriteAction } from './writeBeast';
import { createMapWriteAction } from './writeMap';
import { createNpcSpellWriteActions } from './writeNpcSpell';

export function createWriteActions(deps: UseMediaActionsDeps) {
  return {
    ...createNpcSpellWriteActions(deps),
    addDmMap: createMapWriteAction(deps),
    addDmBeast: createBeastWriteAction(deps),
  };
}
