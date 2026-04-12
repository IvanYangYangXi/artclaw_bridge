// Ref: docs/ui/ui-design.md#Skills
// Batch action bar shown when skills are selected
import { Download, Trash2, Ban, CheckCircle, Pin, X } from 'lucide-react'
import { cn } from '../../utils/cn'
import { useSkillsStore } from '../../stores/skillsStore'

export default function BatchActionBar() {
  const { selectedSkillIds, clearSelection, selectAll, filteredSkills, doInstall, doUninstall, doEnable, doDisable } =
    useSkillsStore()

  const count = selectedSkillIds.size
  if (count === 0) return null

  const total = filteredSkills().length

  const batchAction = async (action: (id: string) => Promise<void>) => {
    const ids = Array.from(selectedSkillIds)
    for (const id of ids) {
      await action(id)
    }
    clearSelection()
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-accent/10 border border-accent/30 rounded-lg mb-4 animate-fade-in">
      <span className="text-small text-accent font-medium">
        已选择 {count} / {total}
      </span>

      <button
        onClick={selectAll}
        className="text-small text-accent hover:text-accent-hover transition-colors"
      >
        全选
      </button>

      <div className="w-px h-4 bg-border-default" />

      <div className="flex items-center gap-1">
        <BatchBtn icon={<Download className="w-3.5 h-3.5" />} label="安装" onClick={() => batchAction(doInstall)} />
        <BatchBtn icon={<CheckCircle className="w-3.5 h-3.5" />} label="启用" onClick={() => batchAction(doEnable)} />
        <BatchBtn icon={<Ban className="w-3.5 h-3.5" />} label="禁用" onClick={() => batchAction(doDisable)} />
        <BatchBtn icon={<Pin className="w-3.5 h-3.5" />} label="钉选" onClick={() => {}} />
        <BatchBtn icon={<Trash2 className="w-3.5 h-3.5" />} label="卸载" onClick={() => batchAction(doUninstall)} danger />
      </div>

      <div className="flex-1" />

      <button
        onClick={clearSelection}
        className="p-1 rounded hover:bg-bg-tertiary text-text-dim hover:text-text-primary transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

function BatchBtn({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ReactNode
  label: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1 px-2 py-1 rounded text-[12px] transition-colors',
        danger
          ? 'text-error hover:bg-error/10'
          : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary',
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}
