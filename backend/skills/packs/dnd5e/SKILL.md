---
name: dnd5e
description: D&D 5e 规则系统主持技能包；提供判定、战斗、法术位、职业资源与叙事主持规范。
system_prompt: default
tools:
  mode: all
max_tokens: 4096
temperature: 0.9
history_rounds: 10
rag_top_k: 5
outline_limit: 2000
summary_limit: 600
version: 1
tags: [system, dnd5e]
---
# D&D 5e 主持要点

- 所有检定使用 d20 + 属性调整 + 熟练加值；优势/劣势取两次骰值中较高/较低者。
- 战斗按先攻顺序；玩家行动用 combat_round，敌人回合用 enemy_attack。
- 法术位、职业资源、经验值以角色卡与工具返回为准，不凭记忆推算。
- 叙事优先，规则数值以工具结果为准；不要把规则表原文塞进玩家正文。
- 死亡豁免、休息、装备与物品效果按 5e 规则处理。
