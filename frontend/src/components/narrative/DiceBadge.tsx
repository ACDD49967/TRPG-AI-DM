/** 骰子结果徽章：成功/失败/暴击的不同配色，并显示后端裁定的优势/劣势。 */
export default function DiceBadge({ data }: {
  data: {
    skill: string; dc: number; roll: number; modifier: number; result: string;
    display?: string; advantage?: string; advantage_note?: string;
  };
}) {
  const ok = ['成功', '大成功', '困难成功', '极限成功', '复活'].includes(data.result);
  const isCrit = ['大成功', '大失败'].includes(data.result) || data.result === '复活';
  const advLabel = data.advantage === 'advantage' ? '优势' : data.advantage === 'disadvantage' ? '劣势' : '';
  const badgeCls = isCrit
    ? ok
      ? 'bg-amber-100 text-amber-700 border-amber-300'
      : 'bg-red-100 text-red-700 border-red-300'
    : ok
      ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
      : 'bg-ink-100 text-ink-500 border-ink-200';
  return (
    <div className="flex items-center gap-2.5 flex-wrap w-fit max-w-full rounded-xl border border-brand-200/70 bg-brand-50/70 px-3.5 py-2.5">
      <span className={`text-2xs font-semibold px-2 py-0.5 rounded-full border ${badgeCls}`}>{data.result}</span>
      {advLabel && (
        <span
          title={data.advantage_note || ''}
          className={`text-2xs font-semibold px-2 py-0.5 rounded-full border ${
            advLabel === '优势'
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-rose-50 text-rose-700 border-rose-200'
          }`}
        >
          {advLabel}
          {/* 来源必须可见：手机上没有 hover，tooltip 等于没写 */}
          {data.advantage_note && (
            <span className="ml-1 font-normal opacity-80">{data.advantage_note}</span>
          )}
        </span>
      )}
      <span className="text-xs text-ink-600">
        {data.display || (
          <>
            {data.skill}：<span className="font-mono font-bold text-ink-800">d20={data.roll}</span>
            {data.modifier !== 0 && <span className="font-mono"> {data.modifier > 0 ? `+${data.modifier}` : data.modifier}</span>}
            <span className="text-ink-500"> vs DC{data.dc}</span>
          </>
        )}
      </span>
    </div>
  );
}
