/** 玩家说明书——详细规则说明，点击打开，不常驻屏幕 */

export default function RulebookModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">玩家说明书</h2>
          <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>
        </div>

        <div className="space-y-4 text-sm text-gray-700 leading-relaxed">
          <section>
            <h3 className="font-bold text-indigo-700 mb-1">一、如何开始</h3>
            <p>1. 在顶部填写 API 地址与 Key，点击「获取模型」选择或输入模型。</p>
            <p>2. 在「剧本」页选择已有剧本、上传剧本切分，或让 AI 自动生成。</p>
            <p>3. 在「角色创建」页完成角色卡：属性、技能、背景、头像。</p>
            <p>4. 在「冒险准备」页确认后点击「开始冒险」。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">二、规则系统</h3>
            <p>支持 D&D 5e、D&D 4e、克苏鲁的呼唤 7e 与自定义规则。</p>
            <p>角色系统与剧本系统相互独立，可自由搭配。</p>
            <p>规则细节通过本地知识库 RAG 按需检索，不占用大量上下文。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">三、角色卡</h3>
            <p>角色卡包含：属性、HP/MP/SAN/AC、技能、特长、背景、头像。</p>
            <p>COC 使用 STR/CON/DEX/INT/POW/CHA/SIZ/EDU 与 HP/MP/SAN/幸运。</p>
            <p>D&D 4e 额外显示回复力与四类防御。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">四、行动与判定</h3>
            <p>用自然语言描述行动，例如“我观察房间”“我尝试撬锁”。</p>
            <p>所有检定由程序通过 dice_roll 完成，AI 不会直接给出结果。</p>
            <p>DC 难度、属性调整、熟练加值均由程序计算。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">五、战斗</h3>
            <p>战斗通过 combat_round 工具结算：攻击、伤害、反击、敌人 HP。</p>
            <p>COC 使用 d100 百分比战斗，D&D 使用 d20 对 AC/防御。</p>
            <p>HP 归零后按对应规则进入濒死/死亡处理。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">六、存档与读档</h3>
            <p>每轮自动存档；游戏中可手动存档。</p>
            <p>回到大厅可载入任意存档，或开启新游戏。</p>
            <p>已有存档不会被自动删除。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">七、知识库 / 扩展包 / 地图 / 图鉴</h3>
            <p>知识库：上传 PDF/DOCX/TXT 或添加备注，AI 按需检索。</p>
            <p>扩展包：手动添加或让 AI 生成，启用后进入知识库。</p>
            <p>地图：上传地区地图，游戏中可查看地点。</p>
            <p>图鉴：查看当前规则系统下的生物，支持自定义图片。</p>
          </section>

          <section>
            <h3 className="font-bold text-indigo-700 mb-1">八、精简模式与深度模式</h3>
            <p>精简模式：保留 5 轮历史，输出更短，适合快速体验。</p>
            <p>深度模式：保留 10 轮历史，输出更长，适合沉浸扮演。</p>
          </section>
        </div>
      </div>
    </div>
  );
}
