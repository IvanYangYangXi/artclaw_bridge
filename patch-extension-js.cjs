/**
 * Roo Code extension.js 直接补丁工具
 * 
 * 直接修改已安装的 extension.js，为 BaseOpenAiCompatibleProvider 添加
 * openAiR1FormatEnabled 支持（交错思考）。
 * 
 * 用法: node patch-extension-js.cjs
 */

const fs = require("fs")
const path = require("path")

// 已安装的 extension.js 路径
const EXTENSION_PATH = path.resolve(
    "C:/Users/yangjili/.vscode/extensions/rooveterinaryinc.roo-cline-3.53.0/dist/extension.js"
)

// 在 extension.js 中定位 BaseOpenAiCompatibleProvider
// 这个类具有以下特征（在源码中）:
// 1. extends BaseProvider (而非 Ra)
// 2. 使用 convertToOpenAiMessages
// 3. 有 createStream 和 createMessage 方法
// 4. 使用 TagMatcher 解析 <think> 标签
// 5. 有 completePrompt 方法
// 6. 不包含 openAiR1FormatEnabled

// 在编译后的代码中，寻找特征:
// - 类名是 minified 的（如 cV, dW 等）
// - 使用 `this.client.chat.completions.create(params, requestOptions)` (两个参数)
// - 在 createMessage 中有 `for await` 循环处理 stream

function findAndPatchBaseOpenAiCompatibleProvider(content) {
    // 搜索 "openAiR1FormatEnabled" 出现的次数
    const r1Count = (content.match(/openAiR1FormatEnabled/g) || []).length
    console.log(`[INFO] 找到 openAiR1FormatEnabled 出现 ${r1Count} 次`)

    if (r1Count === 0) {
        console.log("[ERROR] extension.js 中未找到 openAiR1FormatEnabled!")
        return null
    }

    // 查找 "convertToOpenAiMessages" 模式（在 minified 代码中可能是 xd 函数）
    // 在 cV (OpenAiHandler) 中已经使用了 openAiR1FormatEnabled
    // 我们需要找到另一个使用 convertToOpenAiMessages 但没有 openAiR1FormatEnabled 的类
    
    // 查找所有 "class extends" 的定义
    const classRegex = /var\s+(\w+)\s*=\s*class\s+extends\s+(\w+)/g
    const classes = []
    let match
    while ((match = classRegex.exec(content)) !== null) {
        classes.push({
            name: match[1],
            parent: match[2],
            index: match.index,
            endIndex: findClassEnd(content, match.index)
        })
    }
    
    console.log(`[INFO] 找到 ${classes.length} 个类定义`)
    for (const cls of classes) {
        console.log(`  - var ${cls.name} = class extends ${cls.parent}`)
    }

    // 找出哪些类具有 completePrompt 方法（这是 BaseOpenAiCompatibleProvider 的特征）
    // OpenAiHandler (cV) 也有 completePrompt，但已经支持 openAiR1FormatEnabled
    // 我们需要找另一个有 completePrompt 但没有 openAiR1FormatEnabled 的类
    
    for (const cls of classes) {
        const classCode = content.substring(cls.index, cls.endIndex)
        const hasCompletePrompt = classCode.includes("completePrompt")
        const hasCreateStream = classCode.includes("createStream")
        const hasOpenAiR1 = classCode.includes("openAiR1FormatEnabled")
        
        if (hasCompletePrompt && hasCreateStream && !hasOpenAiR1) {
            console.log(`\n[✓] 找到目标类: ${cls.name} (extends ${cls.parent})`)
            console.log(`    - extends ${cls.parent}`)
            console.log(`    - 有 completePrompt: ${hasCompletePrompt}`)
            console.log(`    - 有 createStream: ${hasCreateStream}`)
            console.log(`    - 有 openAiR1FormatEnabled: ${hasOpenAiR1}`)
            return cls
        }
    }

    return null
}

function findClassEnd(content, startIndex) {
    // 找到类定义的结束位置
    // 在 minified 代码中，类定义通常以 }; 或类似方式结束
    // 通过花括号匹配来找到结束位置
    let braceCount = 0
    let inClass = false
    let i = startIndex
    
    while (i < content.length) {
        const char = content[i]
        if (char === '{') {
            braceCount++
            inClass = true
        } else if (char === '}') {
            braceCount--
            if (inClass && braceCount === 0) {
                // 类定义结束
                return i + 1
            }
        }
        i++
    }
    return content.length
}

function patchClass(content, cls) {
    const classCode = content.substring(cls.index, cls.endIndex)
    
    // 在 createStream 方法的 messages 参数中添加 R1 格式转换
    // 需要找到类似 {...convertToOpenAiMessages(messages)} 的模式
    // 或者 [{role:"system",content:systemPrompt},...convertToOpenAiMessages(messages)]
    
    // 在 minified 代码中，这个模式可能是"system",content: 后面跟一些变量
    
    // 策略: 在类中找到 createStream 方法的 messages 构建部分
    // 然后在其中添加 openAiR1FormatEnabled 检查
    
    // 首先，找到 createStream 方法开始的位置
    const createStreamMatch = classCode.match(/async\s*\*?\s*createStream\s*\(/)
    if (!createStreamMatch) {
        console.log("[ERROR] 在目标类中未找到 createStream 方法")
        return null
    }
    
    const createStreamStart = cls.index + createStreamMatch.index
    
    // 在 createStream 中找到 messages 参数构建
    // 查找 "messages" 赋值
    const searchFromIndex = classCode.indexOf(createStreamMatch[0])
    const afterCreateStream = classCode.substring(searchFromIndex)
    
    // 查找 messages 构建模式: ...messages...convertToOpenAiMessages(messages)
    const msgPattern = afterCreateStream.match(/messages:\s*\[/)
    if (msgPattern) {
        console.log(`[INFO] 在 createStream 中找到 messages 数组: 偏移 ${msgPattern.index}`)
    }
    
    return {
        classCode,
        createStreamOffset: createStreamStart
    }
}

function main() {
    console.log("=".repeat(60))
    console.log("Roo Code DeepSeek 交错思考 - extension.js 补丁工具")
    console.log("=".repeat(60))
    console.log()
    
    // 检查文件是否存在
    if (!fs.existsSync(EXTENSION_PATH)) {
        console.error(`[ERROR] 未找到 extension.js: ${EXTENSION_PATH}`)
        console.error("请确认 Roo Code 已安装且路径正确")
        process.exit(1)
    }
    
    const stats = fs.statSync(EXTENSION_PATH)
    console.log(`[INFO] extension.js 大小: ${(stats.size / 1024 / 1024).toFixed(2)} MB`)
    
    // 读取文件（使用 UTF8，JS 文件通常为 UTF8）
    console.log("[INFO] 正在读取 extension.js...")
    const content = fs.readFileSync(EXTENSION_PATH, "utf8")
    console.log(`[INFO] 读取完成: ${content.length} 字符`)
    
    // 创建备份
    const backupPath = EXTENSION_PATH + ".bak"
    if (!fs.existsSync(backupPath)) {
        console.log("[INFO] 创建备份文件...")
        fs.copyFileSync(EXTENSION_PATH, backupPath)
        console.log(`[INFO] 备份已创建: ${backupPath}`)
    } else {
        console.log("[INFO] 备份文件已存在，跳过")
    }
    
    // 查找目标类
    const targetClass = findAndPatchBaseOpenAiCompatibleProvider(content)
    
    if (!targetClass) {
        console.log("\n[ERROR] 未找到需要打补丁的类")
        console.log("这可能意味着 extension.js 已经包含了所需的修改")
        process.exit(1)
    }
    
    // 获取类代码段
    const classCode = content.substring(targetClass.index, targetClass.endIndex)
    
    // 分析并修改
    const patch = analyzeAndPatch(classCode, targetClass.name)
    if (!patch) {
        process.exit(1)
    }
    
    // 应用补丁
    const patchedContent = content.substring(0, targetClass.index) + patch + content.substring(targetClass.endIndex)
    
    // 验证修改
    const r1CountAfter = (patchedContent.match(/openAiR1FormatEnabled/g) || []).length
    console.log(`\n[验证] openAiR1FormatEnabled 出现次数: ${r1CountAfter}`)
    
    if (r1CountAfter <= (content.match(/openAiR1FormatEnabled/g) || []).length) {
        console.log("[ERROR] 补丁似乎未生效!")
        process.exit(1)
    }
    
    // 写回文件
    console.log("[INFO] 正在写回修改后的 extension.js...")
    fs.writeFileSync(EXTENSION_PATH, patchedContent, "utf8")
    
    console.log("\n" + "=".repeat(60))
    console.log("[✓] 补丁应用成功!")
    console.log("=".repeat(60))
    console.log("\n请重启 VS Code 使修改生效")
    console.log("\n在 Roo Code 设置中:")
    console.log("  1. 选择 API 提供商: OpenAI Compatible")
    console.log("  2. 填写你的中转代理 URL 和 API Key")
    console.log("  3. 填写模型 ID (如 deepseek-reasoner)")
    console.log("  4. 勾选 '启用 R1 格式'")
    console.log("  5. 保存")
}

function analyzeAndPatch(classCode, className) {
    console.log(`\n[INFO] 开始分析 ${className} 类的代码结构...`)
    
    // 检查类是否已有 openAiR1FormatEnabled
    if (classCode.includes("openAiR1FormatEnabled")) {
        console.log("[WARN] 该类已有 openAiR1FormatEnabled，无需补丁")
        return null
    }
    
    // 查找 createStream 方法
    const streamMethods = [
        { pattern: /async\s*\*?\s*createStream\s*\(/, name: "createStream" },
        { pattern: /async\s*\*?\s*createMessage\s*\(/, name: "createMessage" }
    ]
    
    for (const { pattern, name } of streamMethods) {
        const match = classCode.match(pattern)
        if (match) {
            console.log(`[INFO] 找到 ${name} 方法，位于偏移 ${match.index}`)
        } else {
            console.log(`[INFO] 未找到 ${name} 方法`)
        }
    }
    
    // 查找 messages 构建模式
    // 在 minified BaseOpenAiCompatibleProvider 中，messages 构建可能是:
    // [{role:"system",content:X},...xd(Y)]
    // 或 [{role:"system",content:Xg},...xd(V)]
    
    // 查找 system prompt 的 messages 模式
    const msgArrayPattern = /messages:\s*\[\{role:"system",content:(\w+)\},\.\.\.(\w+)\((\w+)\)\]/g
    const matches = [...classCode.matchAll(msgArrayPattern)]
    
    if (matches.length > 0) {
        console.log(`[INFO] 找到 messages 数组模式: ${matches.length} 处`)
        for (const m of matches) {
            console.log(`  匹配: messages: [{role:"system",content:${m[1]}},...${m[2]}(${m[3]})]`)
        }
    }
    
    // 查找另一种模式: (()=>{...})() IIFE 用于 messages
    const iifePattern = /messages:\s*\(\(\s*\)\s*=>\s*\{/
    const iifeMatch = classCode.match(iifePattern)
    if (iifeMatch) {
        console.log(`[INFO] 找到 messages IIFE 模式，位于偏移 ${iifeMatch.index}`)
    }
    
    // 查找 openAiStreamingEnabled 模式
    const streamingPattern = /openAiStreamingEnabled/g
    const streamingMatches = [...classCode.matchAll(streamingPattern)]
    console.log(`[INFO] openAiStreamingEnabled 出现 ${streamingMatches.length} 次`)
    
    // 查找 completePrompt 中的 messages 模式
    const completeMsgPattern = /messages:\s*\[\s*\{role:"user",content:(\w+)\}\s*\]/
    const completeMatch = classCode.match(completeMsgPattern)
    if (completeMatch) {
        console.log(`[INFO] completePrompt 中的 messages: [{role:"user",content:${completeMatch[1]}}]`)
    }
    
    // 查找这个类是否有类似 enableReasoningEffort 的模式
    const reasoningPattern = /enableReasoningEffort/g
    const reasoningMatches = [...classCode.matchAll(reasoningPattern)]
    console.log(`[INFO] enableReasoningEffort 出现 ${reasoningMatches.length} 次`)
    
    // 为了让补丁更健壮，使用字符串替换方法
    // 在 createStream 中，找到 messages 构建部分并添加 R1 格式转换
    
    // 方法: 找到 (()=>{ 的 messages: IIFE 并修改它
    // 如果找到 IIFE 模式，提取它的代码进行分析
    if (iifeMatch) {
        const iifeStart = iifeMatch.index + iifeMatch[0].length
        
        // 查找 IIFE 的结束: })() 或 } ) ( )
        // 但更简单的是找到 })(), 并替换整个 IIFE
        const iifeEnd = classCode.indexOf("})()", iifeStart)
        if (iifeEnd !== -1) {
            const iifeCode = classCode.substring(iifeMatch.index, iifeEnd + 4)
            console.log(`\n[INFO] IIFE 代码片段 (${iifeCode.length} 字符):`)
            console.log(`  ${iifeCode.substring(0, 200)}...`)
            
            // 检查这个 IIFE 是否包含 convertToOpenAiMessages
            if (iifeCode.includes("convertToOpenAiMessages") || 
                (() => {
                    // 在 minified 代码中查找类似 xd() 的函数调用
                    const funcCallMatch = iifeCode.match(/\.\.\.(\w+)\((\w+)\)\]\s*\}\s*\)\(\)/)
                    return funcCallMatch !== null
                })()) {
                
                // 这是 BaseOpenAiCompatibleProvider 的 messages 构建
                // 需要将其替换为包含 openAiR1FormatEnabled 检查的版本
                
                // 构建新的 IIFE
                const newIIFE = buildPatchedIIFE(iifeCode, className)
                if (newIIFE) {
                    console.log("\n[PATCH] 正在应用补丁...")
                    
                    // 在类代码中替换
                    const patchedClass = classCode.substring(0, iifeMatch.index) + newIIFE + classCode.substring(iifeEnd + 4)
                    
                    console.log("[✓] 补丁已应用到类代码")
                    
                    // 也需要在 completePrompt 中添加 thinking 参数
                    const patchedClass2 = patchCompletePrompt(patchedClass, className)
                    
                    return patchedClass2
                }
            }
        }
    }
    
    // 如果 IIFE 模式未找到或无法处理，尝试其他方法
    // 直接修改 messages 数组
    if (matches.length > 0) {
        const m = matches[0]
        const sysVar = m[1]  // system prompt 变量
        const funcVar = m[2] // convertToOpenAiMessages 函数
        const msgVar = m[3]  // messages 变量
        
        // 构建新的 messages 部分
        const newMessagesCode = `messages: (() => {\nif (this.options.openAiR1FormatEnabled) {\nconst t = convertToR1Format([{role:"user",content:${sysVar}},...${msgVar}],{mergeToolResultText:true});\nreturn ${funcVar}(t);\n}\nreturn [{role:"system",content:${sysVar}},...${funcVar}(${msgVar})];\n})()`
        
        console.log(`\n[PATCH] 替换 messages 部分...`)
        console.log(`  旧: messages: [{role:"system",content:${sysVar}},...${funcVar}(${msgVar})]`)
        
        const patchedClass = classCode.replace(m[0], newMessagesCode)
        
        // 在 createStream 中添加 thinking 参数注入
        const patchedClass2 = addThinkingToCreateStream(patchedClass)
        
        // 在 completePrompt 中添加 thinking 参数注入  
        const patchedClass3 = patchCompletePrompt(patchedClass2, className)
        
        return patchedClass3
    }
    
    console.log("[ERROR] 无法定位 messages 构建代码，补丁失败")
    console.log("这可能是由于代码结构不匹配。请尝试从源码构建。")
    return null
}

function buildPatchedIIFE(originalIIFE, className) {
    // 从 IIFE 中提取变量名
    // 原始格式类似: (() => { return [{role:"system",content:X},...Y(Z)] })()
    const fullMatch = originalIIFE.match(/messages:\s*\(\(\s*\)\s*=>\s*\{[^}]*return\s+\[([^\]]+)\]\s*\}\s*\)\(\)/)
    if (!fullMatch) {
        console.log("[ERROR] 无法解析 IIFE 结构")
        console.log(`IIFE: ${originalIIFE.substring(0, 300)}`)
        return null
    }
    
    // 从 return 语句中提取变量
    const returnContent = fullMatch[1]
    const sysMatch = returnContent.match(/\{role:"system",content:(\w+)\}/)
    const funcMatch = returnContent.match(/\.\.\.(\w+)\((\w+)\)/)
    
    if (!sysMatch || !funcMatch) {
        console.log("[ERROR] 无法从 IIFE 中提取变量")
        console.log(`return 内容: ${returnContent}`)
        return null
    }
    
    const sysVar = sysMatch[1]
    const funcVar = funcMatch[1]
    const msgVar = funcMatch[2]
    
    console.log(`[INFO] IIFE 变量: systemPrompt=${sysVar}, func=${funcVar}, messages=${msgVar}`)
    
    // 构建新的 IIFE
    const newIIFE = `messages: (()=>{if(this.options.openAiR1FormatEnabled){const t=convertToR1Format([{role:"user",content:${sysVar}},...${msgVar}],{mergeToolResultText:true});return ${funcVar}(t)}return [{role:"system",content:${sysVar}},...${funcVar}(${msgVar})]})()`
    
    return newIIFE
}

function addThinkingToCreateStream(classCode) {
    // 在 createStream 中找到合适的位置添加 thinking 参数注入
    // 查找 `tool_choice:` 或 `parallel_tool_calls:` 之后
    const patterns = [
        /parallel_tool_calls:[^,}]+\}/,
        /parallel_tool_calls:[^,}]+,/,
        /tool_choice:[^,}]+,/
    ]
    
    for (const pattern of patterns) {
        const match = classCode.match(pattern)
        if (match) {
            const insertPos = match.index + match[0].length
            const insertCode = `\n// [PATCH] openAiR1FormatEnabled: auto thinking\nif(this.options.openAiR1FormatEnabled){;(params).thinking={type:"enabled"}}`
            
            console.log(`[PATCH] 在 ${match[0].substring(0, 40)}... 后注入 thinking 参数`)
            return classCode.substring(0, insertPos) + insertCode + classCode.substring(insertPos)
        }
    }
    
    console.log("[WARN] 无法在 createStream 中找到插入 thinking 的位置")
    return classCode
}

function patchCompletePrompt(classCode, className) {
    // 在 completePrompt 方法的 messages 赋值后添加 thinking 参数注入
    // completePrompt 中的模式: messages: [{role:"user",content:X}]
    const msgPattern = /messages:\s*\[\s*\{role:"user",content:(\w+)\}\s*\]/
    const match = classCode.match(msgPattern)
    
    if (match) {
        const insertPos = match.index + match[0].length
        const insertCode = `\n// [PATCH] openAiR1FormatEnabled: auto thinking (completePrompt)\nif(this.options.openAiR1FormatEnabled){;(params).thinking={type:"enabled"}}`
        
        console.log(`[PATCH] completePrompt: 在 messages 后注入 thinking 参数`)
        return classCode.substring(0, insertPos) + insertCode + classCode.substring(insertPos)
    }
    
    console.log("[WARN] 无法在 completePrompt 中找到插入位置")
    return classCode
}

main()
