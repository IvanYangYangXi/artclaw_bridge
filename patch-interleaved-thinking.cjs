#!/usr/bin/env node
/**
 * Roo Code DeepSeek 交错思考补丁工具
 * 
 * 为 OpenAI Compatible 提供商添加 DeepSeek 交错思考支持。
 * 
 * 修改原理:
 *   在 base-openai-compatible-provider.ts 的 createStream 方法中:
 *   1. 导入 convertToR1Format (参考 deepseek.ts:15)
 *   2. 当 openAiR1FormatEnabled=true 时，用 convertToR1Format 转换消息 (参考 deepseek.ts:70-72)
 *   3. 自动注入 thinking: { type: "enabled" } (参考 deepseek.ts:81)
 * 
 * 注意: provider-settings.ts 和 OpenAICompatible.tsx 已包含 openAiR1FormatEnabled 字段和 UI
 */

const fs = require("fs")
const path = require("path")

const REPO_DIR = path.resolve(__dirname, "..")
const BACKUP_SUFFIX = ".bak"

// ============================================================
// 补丁: base-openai-compatible-provider.ts
// ============================================================
function patchSourceFile(filePath) {
    if (!fs.existsSync(filePath)) {
        console.error(`❌ 文件不存在: ${filePath}`)
        return false
    }

    const original = fs.readFileSync(filePath, "utf8")

    // 检查是否已打补丁
    if (original.includes("// [PATCH] openAiR1FormatEnabled")) {
        console.log("✅ 文件已打过补丁，跳过")
        return true
    }

    // === 修改 1: 添加 convertToR1Format 导入 ===
    let patched = original

    const importLine = `import { convertToOpenAiMessages } from "../transform/openai-format"`
    const patchedImportLine = `import { convertToOpenAiMessages } from "../transform/openai-format"\nimport { convertToR1Format } from "../transform/r1-format"`

    if (patched.includes(patchedImportLine)) {
        console.log("  ✅ 导入已存在")
    } else if (patched.includes(importLine)) {
        patched = patched.replace(importLine, patchedImportLine)
        console.log("  ✅ 已添加 convertToR1Format 导入")
    } else {
        console.log("  ⚠️ 未找到标准导入行，搜索替代...")
        // 在最后一条 import 后插入
        const importEnd = patched.lastIndexOf("\n", patched.lastIndexOf("from"))
        if (importEnd > 0) {
            const insertAt = patched.indexOf("\n", importEnd + 1)
            patched = patched.slice(0, insertAt + 1) +
                `import { convertToR1Format } from "../transform/r1-format"\n` +
                patched.slice(insertAt + 1)
            console.log("  ✅ 已通过备用方式添加导入")
        }
    }

    // === 修改 2: 替换 messages 构建 + 添加 R1 格式转换 ===
    const messagesPattern = /messages:\s*\[\s*\{\s*role:\s*"system",\s*content:\s*systemPrompt\s*\}\s*,\s*\.\.\.convertToOpenAiMessages\(\s*messages\s*\)\s*\]/

    const patchedMessages = `messages: (() => {
            // [PATCH] openAiR1FormatEnabled: 为 DeepSeek 推理模型启用 R1 格式转换
            // 参考: deepseek.ts:70-72
            if (this.options.openAiR1FormatEnabled) {
                const converted = convertToR1Format(
                    [{ role: "user", content: systemPrompt }, ...messages],
                    { mergeToolResultText: true }
                )
                return convertToOpenAiMessages(converted)
            }
            return [{ role: "system", content: systemPrompt }, ...convertToOpenAiMessages(messages)]
        })()`

    if (patched.includes("// [PATCH] openAiR1FormatEnabled")) {
        console.log("  ✅ 消息转换已存在")
    } else if (messagesPattern.test(patched)) {
        patched = patched.replace(messagesPattern, patchedMessages)
        console.log("  ✅ 已注入 R1 格式消息转换")
    } else {
        console.log("  ⚠️ 未匹配到标准 messages 模式")
    }

    // === 修改 3: 添加 thinking 参数注入 (使用正则匹配，兼容制表符/空格) ===
    // 在 createStream 中的 enableReasoningEffort 检查之后添加
    const createStreamThinkingRegex = /(\t*\/\/ Add thinking parameter if reasoning is enabled and model supports it\n\t*if\s*\(\s*this\.options\.enableReasoningEffort\s*&&\s*info\.supportsReasoningBinary\s*\)\s*\{\n\t*;\(params as any\)\.thinking\s*=\s*\{\s*type:\s*"enabled"\s*\}\n\t*\})/

    const createStreamThinkingReplacement = `$1
\t\t// [PATCH] openAiR1FormatEnabled: 自动启用 thinking 模式
\t\tif (this.options.openAiR1FormatEnabled) {
\t\t\t;(params as any).thinking = { type: "enabled" }
\t\t}`

    if (patched.includes("// [PATCH] openAiR1FormatEnabled: 自动启用 thinking")) {
        console.log("  ✅ createStream thinking 注入已存在")
    } else if (createStreamThinkingRegex.test(patched)) {
        patched = patched.replace(createStreamThinkingRegex, createStreamThinkingReplacement)
        console.log("  ✅ 已注入 createStream thinking 参数")
    } else {
        console.log("  ⚠️ 未找到 createStream enableReasoningEffort 代码块")
    }

    // === 同样修改 completePrompt 方法 ===
    const completePromptThinkingRegex = /(\t*\/\/ Add thinking parameter if reasoning is enabled and model supports it\n\t*if\s*\(\s*this\.options\.enableReasoningEffort\s*&&\s*modelInfo\.supportsReasoningBinary\s*\)\s*\{\n\t*;\(params as any\)\.thinking\s*=\s*\{\s*type:\s*"enabled"\s*\}\n\t*\})/

    const completePromptThinkingReplacement = `$1
\t\t// [PATCH] openAiR1FormatEnabled: 自动启用 thinking (completePrompt)
\t\tif (this.options.openAiR1FormatEnabled) {
\t\t\t;(params as any).thinking = { type: "enabled" }
\t\t}`

    if (patched.includes("// [PATCH] openAiR1FormatEnabled: 自动启用 thinking (completePrompt)")) {
        console.log("  ✅ completePrompt thinking 注入已存在")
    } else if (completePromptThinkingRegex.test(patched)) {
        patched = patched.replace(completePromptThinkingRegex, completePromptThinkingReplacement)
        console.log("  ✅ 已注入 completePrompt thinking 参数")
    } else {
        console.log("  ⚠️ 未找到 completePrompt enableReasoningEffort 代码块")
    }

    if (patched === original) {
        console.log("⚠️ 文件未发生任何变化")
        return false
    }

    // 写回文件
    fs.writeFileSync(filePath + BACKUP_SUFFIX, original, "utf8")
    fs.writeFileSync(filePath, patched, "utf8")
    
    console.log(`💾 已备份原文件到 ${path.basename(filePath)}${BACKUP_SUFFIX}`)
    return true
}

// ============================================================
// 验证
// ============================================================
function verifyPatch(filePath) {
    const content = fs.readFileSync(filePath, "utf8")
    const checks = [
        ["convertToR1Format 导入", content.includes('import { convertToR1Format }')],
        ["消息转换 (openAiR1FormatEnabled)", content.includes("// [PATCH] openAiR1FormatEnabled")],
        ["mergeToolResultText: true", content.includes("mergeToolResultText: true")],
        ["createStream thinking 注入", content.includes("// [PATCH] openAiR1FormatEnabled: 自动启用 thinking")],
        ["completePrompt thinking 注入", content.includes("// [PATCH] openAiR1FormatEnabled: 自动启用 thinking (completePrompt)")],
    ]

    let allPass = true
    console.log("\n🔍 验证结果:")
    for (const [name, passed] of checks) {
        console.log(`  ${passed ? "✅" : "❌"} ${name}`)
        if (!passed) allPass = false
    }
    return allPass
}

// ============================================================
// 主流程
// ============================================================
function main() {
    console.log("╔══════════════════════════════════════════════╗")
    console.log("║  Roo Code DeepSeek 交错思考补丁工具        ║")
    console.log("╚══════════════════════════════════════════════╝\n")

    const sourceFile = path.join(REPO_DIR, "base-openai-compatible-provider.ts")
    const extensionDist = "C:\\Users\\JKLIL\\.vscode\\extensions\\rooveterinaryinc.roo-cline-3.53.0\\dist\\extension.js"

    // 阶段 1: 修补 TypeScript 源码
    console.log("📁 阶段 1: 修补 TypeScript 源码")
    console.log(`   文件: ${sourceFile}\n`)

    if (!fs.existsSync(sourceFile)) {
        console.error("❌ 源文件不存在!")
        console.error(`   请确认 ${sourceFile} 存在`)
        process.exit(1)
    }

    const patched = patchSourceFile(sourceFile)
    if (!patched) {
        console.log("\n⚠️ 补丁未应用 (可能已存在)")
    }

    // 验证
    const verified = verifyPatch(sourceFile)
    if (!verified && patched) {
        console.log("\n❌ 验证失败! 正在恢复备份...")
        const backup = sourceFile + BACKUP_SUFFIX
        if (fs.existsSync(backup)) {
            fs.copyFileSync(backup, sourceFile)
            fs.unlinkSync(backup)
        }
        process.exit(1)
    }

    console.log(`\n${verified ? "✅" : "⚠️"} 补丁验证${verified ? "通过" : "部分失败"}`)

    // 阶段 2: 尝试直接修补已安装的 extension.js
    if (fs.existsSync(extensionDist)) {
        console.log(`\n📁 阶段 2: 尝试修补已安装的 extension.js`)
        console.log(`   文件: ${extensionDist}\n`)
        
        try {
            // 注意: extension.js 是 minified bundle, 直接修改很脆弱
            // 如果补丁成功, 用户可立即重启 VS Code 生效
            // 如果失败, 用户需通过编译源码的方式获得完整 extension.js
            
            const extJsContent = fs.readFileSync(extensionDist, "utf8")
            
            // 检查是否已有 DeepSeek 相关代码
            if (extJsContent.includes("convertToR1Format")) {
                console.log("  ✅ extension.js 中找到了 convertToR1Format 函数")
                
                // 备份
                const backupJs = extensionDist + BACKUP_SUFFIX
                if (!fs.existsSync(backupJs)) {
                    fs.copyFileSync(extensionDist, backupJs)
                    console.log(`  💾 已备份 extension.js`)
                }
                
                // 查找并修补 thinking 注入代码
                // 原始: (this.options.enableReasoningEffort && ... ) && (param.thinking = {type:"enabled"})
                // 改成: (this.options.enableReasoningEffort && ... || this.options.openAiR1FormatEnabled) && (param.thinking = {type:"enabled"})
                
                const thinkPattern = /this\.options\.enableReasoningEffort\s*&&\s*(\w+)\.supportsReasoningBinary\s*&&\s*\((\w+)\.thinking\s*=\s*\{\s*type\s*:\s*["']enabled["']\s*\}\)/g
                
                if (thinkPattern.test(extJsContent)) {
                    const newContent = extJsContent.replace(
                        thinkPattern,
                        `(this.options.enableReasoningEffort&&$1.supportsReasoningBinary||this.options.openAiR1FormatEnabled)&&($2.thinking={type:"enabled"})`
                    )
                    fs.writeFileSync(extensionDist, newContent, "utf8")
                    console.log("  ✅ 已修补 extension.js 中的 thinking 参数注入")
                } else {
                    console.log("  ⚠️ 未找到 thinking 注入代码，跳过 extension.js 补丁")
                }
            } else {
                console.log("  ⚠️ extension.js 中未包含 convertToR1Format")
                console.log("  (DeepSeek 处理器可能未打包在此文件中)")
            }
        } catch (e) {
            console.log(`  ⚠️ extension.js 修补失败: ${e.message}`)
        }
    } else {
        console.log("\n⚠️ 未找到已安装的 extension.js")
        console.log("   请先安装 Roo Code 扩展")
    }

    // 最终提示
    console.log("\n")
    console.log("╔══════════════════════════════════════════════╗")
    console.log("║  📋 使用说明                                ║")
    console.log("╠══════════════════════════════════════════════╣")
    console.log("║                                              ║")
    console.log("║  1. 重启 VS Code 使补丁生效                  ║")
    console.log("║                                              ║")
    console.log("║  2. 在 Roo Code 设置中:                      ║")
    console.log("║     • 选择 OpenAI Compatible 提供商           ║")
    console.log("║     • 填写你的第三方中转 URL 和 API Key      ║")
    console.log("║     • 填写模型 ID (如 deepseek-v4)           ║")
    console.log("║     • 勾选「启用 R1 格式」                    ║")
    console.log("║     • 保存                                  ║")
    console.log("║                                              ║")
    console.log("║  3. 当 Roo Code 更新后:                      ║")
    console.log("║     重新运行此脚本即可                       ║")
    console.log('║     node "roocode补丁/patch-interleaved-thinking.cjs"  ║')
    console.log("║                                              ║")
    console.log("╚══════════════════════════════════════════════╝")
}

main()
