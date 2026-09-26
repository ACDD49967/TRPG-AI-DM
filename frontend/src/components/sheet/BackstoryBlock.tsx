/** 背景故事（保留原换行）。 */
export default function BackstoryBlock({ text }: { text: string }) {
  return (
    <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
      <p className="section-label mb-1">背景故事</p>
      <p className="text-xs text-ink-700 leading-relaxed whitespace-pre-wrap">{text}</p>
    </div>
  );
}
