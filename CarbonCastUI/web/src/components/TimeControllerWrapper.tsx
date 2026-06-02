
export default function TimeControllerWrapper(){
  return (
    <div className="pointer-events-auto fixed inset-x-0 bottom-0 flex justify-center pb-4 sm:inset-auto sm:bottom-6">
      <div className="rounded-2xl border border-[var(--glassBorder)] bg-[var(--glassBg)] p-3 backdrop-blur-xl text-[var(--text)]">
        <div className="text-sm text-[var(--muted)]">Time controls</div>
        <div className="text-xs text-[var(--muted)]">TODO: Hook up timeline UI here</div>
      </div>
    </div>
  )
}


