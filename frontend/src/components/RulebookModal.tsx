/** 玩家说明书 —— 弹窗内分节展示规则与操作说明，随开随用不常驻屏幕 */

import Modal from './ui/Modal';

const SECTIONS: Array<{ icon: string; title: string; items: string[] }> = [
  {
    icon: '🎬',
    title: '如何开始',
    items: [
      '在顶部填写 API 地址与 Key，点击「获取模型」选择或输入模型。',
      '在「剧本」页选择已有剧本、上传剧本切分，或让 AI 自动生成。',
      '在「角色创建」页完成角色卡：属性、技能、背景、头像。',
      '在「冒险准备」页确认后点击「开始冒险」。',
    ],
  },
  {
    icon: '📖',
    title: '规则系统',
    items: [
      '支持 D&D 5e、D&D 4e、克苏鲁的呼唤 7e 与自定义规则。',
      '角色系统与剧本系统必须一致：5e 角色用 5e 剧本，4e 用 4e，COC 用 COC。',
      '角色卡库不绑定剧本：同一张 5e 角色卡可以用于任何 5e 剧本。',
      '规则细节通过本地知识库 RAG 按需检索，不占用大量上下文。',
    ],
  },
  {
    icon: '🧝',
    title: '角色卡',
    items: [
      '包含属性、HP/AC（COC 额外 MP/SAN/幸运）、技能、特长、背景、头像。',
      'COC 使用 STR/CON/DEX/INT/POW/CHA/SIZ/EDU 与 HP/MP/SAN/幸运。',
      'D&D 4e 额外显示回复力与四类防御。',
    ],
  },
  {
    icon: '🎲',
    title: '行动与判定',
    items: [
      '用自然语言描述行动，例如「我观察房间」「我尝试撬锁」。',
      '所有检定由程序通过 dice_roll 完成，AI 不会直接给出结果。',
      'DC 难度、属性调整、熟练加值均由程序计算。',
    ],
  },
  {
    icon: '⚔️',
    title: '战斗',
    items: [
      '战斗通过 combat_round 工具结算：攻击、伤害、反击、敌人 HP。',
      'COC 使用 d100 百分比战斗，D&D 使用 d20 对 AC/防御。',
      'HP 归零后按对应规则进入濒死/死亡处理。',
    ],
  },
  {
    icon: '💾',
    title: '存档与读档',
    items: ['每轮自动存档；游戏中可手动存档。', '回到大厅可载入任意存档，或开启新游戏。', '已有存档不会被自动删除。'],
  },
  {
    icon: '🗺️',
    title: '知识库 / 扩展包 / 地图 / 图鉴',
    items: [
      '知识库：上传 PDF/DOCX/TXT 或添加备注，AI 按需检索。',
      '扩展包：手动添加或让 AI 生成，启用后进入知识库。',
      '地图：上传地区地图，游戏中可查看地点。',
      '图鉴：查看当前规则系统下的生物，支持自定义图片。',
    ],
  },
  {
    icon: '⚙️',
    title: '精简模式与深度模式',
    items: ['精简模式：保留 5 轮历史，输出更短，适合快速体验。', '深度模式：保留 10 轮历史，输出更长，适合沉浸扮演。'],
  },
];

export default function RulebookModal({ onClose }: { onClose: () => void }) {
  return (
    <Modal
      open
      onClose={onClose}
      paper
      size="xl"
      icon="📕"
      title="玩家说明书"
      subtitle="从连接模型到掷骰判定，一页看懂全部玩法"
      footer={
        <button onClick={onClose} className="btn-primary text-sm">
          开始冒险
        </button>
      }
    >
      <div className="space-y-5">
        {SECTIONS.map((s, i) => (
          <section key={s.title} className="relative pl-9">
            <span
              className="absolute left-0 top-0 w-6 h-6 rounded-lg bg-white/70 border border-parch-400/60
                         flex items-center justify-center text-xs font-bold text-parch-700"
              aria-hidden
            >
              {i + 1}
            </span>
            <h3 className="font-bold text-parch-700 mb-1.5 flex items-center gap-1.5">
              <span aria-hidden>{s.icon}</span>
              {s.title}
            </h3>
            <ul className="space-y-1">
              {s.items.map((t, j) => (
                <li key={j} className="text-sm text-ink-700 leading-relaxed flex gap-2">
                  <span className="text-parch-500 shrink-0 mt-2 w-1 h-1 rounded-full bg-parch-500" aria-hidden />
                  <span>{t}</span>
                </li>
              ))}
            </ul>
            {i < SECTIONS.length - 1 && <div className="paper-rule mt-5" />}
          </section>
        ))}
      </div>
    </Modal>
  );
}
