// Shared syntax rules help panel for filter editors
import { useState } from 'react'
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'

const PATH_VARIABLES = [
  {
    name: '$project_root',
    desc_zh: 'ArtClaw 项目源码根目录',
    desc_en: 'ArtClaw project source root',
    source: '~/.artclaw/config.json → project_root',
    example: '$project_root/tools/**/*',
  },
  {
    name: '$tools_dir',
    desc_zh: '用户工具安装目录',
    desc_en: 'User tools install directory',
    source: '~/.artclaw/tools',
    example: '$tools_dir/user/**/*',
  },
  {
    name: '$skills_installed',
    desc_zh: 'Skill 安装目录',
    desc_en: 'Installed skills directory',
    source: '~/.openclaw/workspace/skills',
    example: '$skills_installed/**/*.md',
  },
  {
    name: '$home',
    desc_zh: '用户主目录',
    desc_en: 'User home directory',
    source: '~',
    example: '$home/.artclaw/config.json',
  },
]

// Standard glob syntax rules
const GLOB_RULES_ZH = [
  { pattern: '*',           desc: '匹配当前目录下任意文件名（不含路径分隔符）' },
  { pattern: '**',          desc: '匹配任意层级子目录（必须独占一段，如 a/**/b）' },
  { pattern: '?',           desc: '匹配任意单个字符（不含路径分隔符）' },
  { pattern: '[abc]',       desc: '字符集，匹配 a、b 或 c 中的任意一个' },
  { pattern: '[a-z]',       desc: '字符范围，匹配 a 到 z 中的任意一个' },
  { pattern: '**/*.py',     desc: '递归匹配所有 .py 文件（推荐写法）' },
  { pattern: '**/*.py ❌ **/*.{py,md}', desc: '不支持花括号扩展，多扩展名请分多行填写' },
]

const GLOB_RULES_EN = [
  { pattern: '*',           desc: 'Matches any filename in current dir (no separators)' },
  { pattern: '**',          desc: 'Matches any depth of subdirectories (must occupy full segment)' },
  { pattern: '?',           desc: 'Matches any single character (no separators)' },
  { pattern: '[abc]',       desc: 'Character set: matches a, b, or c' },
  { pattern: '[a-z]',       desc: 'Character range: matches a through z' },
  { pattern: '**/*.py',     desc: 'Recursively match all .py files (recommended)' },
  { pattern: '**/*.py ❌ **/*.{py,md}', desc: 'Brace expansion not supported — use separate lines for multiple extensions' },
]

export default function PathVariablesHelp({ language }: { language: string }) {
  const [expanded, setExpanded] = useState(false)
  const zh = language === 'zh'

  return (
    <div className="pt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-accent/80 hover:text-accent transition-colors"
      >
        <HelpCircle className="w-3 h-3" />
        <span>{zh ? '语法规则' : 'Syntax Rules'}</span>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>

      {expanded && (
        <div className="mt-2 rounded border border-border-default bg-bg-quaternary p-3 text-[11px] space-y-4">

          {/* Section 1: Glob syntax */}
          <div>
            <p className="text-text-secondary font-medium mb-1.5">
              {zh ? 'Glob 语法（标准 fnmatch/gitignore 规则）' : 'Glob Syntax (standard fnmatch / gitignore rules)'}
            </p>
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-left text-text-dim border-b border-border-default">
                  <th className="py-1 pr-3">{zh ? '语法' : 'Syntax'}</th>
                  <th className="py-1">{zh ? '说明' : 'Description'}</th>
                </tr>
              </thead>
              <tbody>
                {(zh ? GLOB_RULES_ZH : GLOB_RULES_EN).map((r, i) => (
                  <tr key={i} className="border-b border-border-default/40">
                    <td className="py-1.5 pr-3">
                      <code className="text-accent bg-bg-tertiary px-1 rounded whitespace-nowrap">{r.pattern}</code>
                    </td>
                    <td className="py-1.5 text-text-secondary">{r.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-text-dim mt-1.5">
              {zh
                ? '⚠️ 不支持花括号 {a,b,c}（bash 扩展语法）。多个扩展名请逐行填写独立规则。'
                : '⚠️ Brace expansion {a,b,c} is not supported (bash-only syntax). Use separate lines for multiple extensions.'}
            </p>
          </div>

          {/* Section 2: Path variables */}
          <div>
            <p className="text-text-secondary font-medium mb-1.5">
              {zh ? '路径变量（运行时自动解析为绝对路径）' : 'Path Variables (resolved to absolute paths at runtime)'}
            </p>
            <table className="w-full text-[11px]">
              <thead>
                <tr className="text-left text-text-dim border-b border-border-default">
                  <th className="py-1 pr-2">{zh ? '变量' : 'Variable'}</th>
                  <th className="py-1 pr-2">{zh ? '说明' : 'Description'}</th>
                  <th className="py-1 pr-2">{zh ? '解析来源' : 'Source'}</th>
                  <th className="py-1">{zh ? '示例' : 'Example'}</th>
                </tr>
              </thead>
              <tbody>
                {PATH_VARIABLES.map((v) => (
                  <tr key={v.name} className="border-b border-border-default/40">
                    <td className="py-1.5 pr-2">
                      <code className="text-accent bg-bg-tertiary px-1 rounded">{v.name}</code>
                    </td>
                    <td className="py-1.5 pr-2 text-text-secondary">{zh ? v.desc_zh : v.desc_en}</td>
                    <td className="py-1.5 pr-2 text-text-dim font-mono">{v.source}</td>
                    <td className="py-1.5 text-text-dim font-mono">{v.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-text-dim mt-1.5">
              {zh
                ? '💡 变量未配置（如 $project_root 为空）时，该条规则静默跳过，不报错。'
                : '💡 If a variable is not configured (e.g. $project_root is empty), the rule is silently skipped.'}
            </p>
          </div>

          {/* Section 3: Examples */}
          <div>
            <p className="text-text-secondary font-medium mb-1.5">
              {zh ? '正确示例' : 'Valid Examples'}
            </p>
            <div className="space-y-1">
              {[
                '$skills_installed/**/*.py',
                '$skills_installed/**/*.md',
                '$skills_installed/**/*.json',
                '$project_root/skills/**/*.py',
                '$project_root/tools/**/*',
              ].map((ex) => (
                <div key={ex}>
                  <code className="text-accent bg-bg-tertiary px-1.5 py-0.5 rounded">{ex}</code>
                </div>
              ))}
            </div>
            <p className="text-text-dim mt-1.5">
              {zh
                ? '✅ 多扩展名时每个扩展名单独一行（如上）。不要写 *.{py,md,json}。'
                : '✅ For multiple extensions, add one rule per extension (as above). Do not write *.{py,md,json}.'}
            </p>
          </div>

        </div>
      )}
    </div>
  )
}
