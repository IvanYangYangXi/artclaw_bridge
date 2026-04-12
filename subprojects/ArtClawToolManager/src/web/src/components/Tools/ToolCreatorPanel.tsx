// Ref: docs/features/phase4-tool-creator.md
// Tool creator panel: 3 creation methods
import { Package, Code, Layers, ArrowRight } from 'lucide-react'
import { cn } from '../../utils/cn'

interface ToolCreatorPanelProps {
  onSelectMethod?: (method: 'skill_wrapper' | 'script' | 'composite') => void
}

const METHODS = [
  {
    key: 'skill_wrapper' as const,
    title: '包装 Skill',
    description: '将现有 Skill 包装为带固定参数的快捷工具。选择一个 Skill，配置暴露和固定的参数即可。',
    icon: Package,
    color: 'text-accent',
    bgColor: 'bg-accent/10',
    borderColor: 'hover:border-accent/50',
    example: '例: 将 comfyui-txt2img 包装为固定 1024x1024 的快速文生图',
  },
  {
    key: 'script' as const,
    title: '编写脚本',
    description: '用 Python + artclaw_sdk 编写自定义逻辑脚本。AI 将协助你完成代码编写和测试。',
    icon: Code,
    color: 'text-success',
    bgColor: 'bg-success/10',
    borderColor: 'hover:border-success/50',
    example: '例: 批量导出 FBX、自动重命名资产、一键清理场景',
  },
  {
    key: 'composite' as const,
    title: '组合工具',
    description: '将多个已有工具串联成工作流。定义执行顺序和参数映射关系。',
    icon: Layers,
    color: 'text-warning',
    bgColor: 'bg-warning/10',
    borderColor: 'hover:border-warning/50',
    example: '例: 先命名检查 → 通过后批量导出 → 自动压缩贴图',
  },
]

export default function ToolCreatorPanel({ onSelectMethod }: ToolCreatorPanelProps) {
  return (
    <div className="py-6">
      <div className="text-center mb-8">
        <h2 className="text-lg font-medium text-text-primary mb-2">创建新工具</h2>
        <p className="text-small text-text-secondary">
          选择一种创建方式，AI 将在对话面板中引导你完成工具创建
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-4xl mx-auto">
        {METHODS.map((method) => {
          const Icon = method.icon
          return (
            <button
              key={method.key}
              onClick={() => onSelectMethod?.(method.key)}
              className={cn(
                'flex flex-col items-start p-6 rounded-lg border border-border-default',
                'bg-bg-secondary transition-all text-left',
                'hover:bg-bg-tertiary',
                method.borderColor,
                'group',
              )}
            >
              <div className={cn('p-3 rounded-lg mb-4', method.bgColor)}>
                <Icon className={cn('w-6 h-6', method.color)} />
              </div>

              <h3 className="text-body font-medium text-text-primary mb-2 flex items-center gap-2">
                {method.title}
                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-text-dim" />
              </h3>

              <p className="text-small text-text-secondary mb-3 leading-relaxed">
                {method.description}
              </p>

              <p className="text-[11px] text-text-dim italic">
                {method.example}
              </p>
            </button>
          )
        })}
      </div>
    </div>
  )
}
