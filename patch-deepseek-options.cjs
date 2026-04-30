/**
 * Roo Code DeepSeek 高级选项补丁
 * 
 * 为 DeepSeek 提供商添加以下自定义选项：
 * - Context Window (上下文窗口大小，V4 支持最大 1M)
 * - Max Output Tokens (最大输出 Token 数)
 * 
 * 修改两个文件：
 * 1. webview-ui/build/assets/index.js - 添加 UI 输入框
 * 2. dist/extension.js - 让 getModel() 使用自定义值
 * 
 * 用法: node patch-deepseek-options.cjs
 */

const fs = require("fs")
const path = require("path")

const EXTENSION_DIR = "C:/Users/yangjili/.vscode/extensions/rooveterinaryinc.roo-cline-3.53.0"
const WEBVIEW_PATH = path.join(EXTENSION_DIR, "webview-ui/build/assets/index.js")
const EXTENSION_PATH = path.join(EXTENSION_DIR, "dist/extension.js")

// ============================================================
// Part 1: Patch Webview UI - Add Context Window & Max Output Tokens inputs
// ============================================================
function patchWebviewUI() {
    console.log("\n" + "=".repeat(60))
    console.log("Part 1: 修补 Webview UI")
    console.log("=".repeat(60))

    if (!fs.existsSync(WEBVIEW_PATH)) {
        console.error("[ERROR] 未找到 webview index.js:", WEBVIEW_PATH)
        return false
    }

    let content = fs.readFileSync(WEBVIEW_PATH, "utf8")

    // 备份
    const backupPath = WEBVIEW_PATH + ".bak-deepseek-options"
    if (!fs.existsSync(backupPath)) {
        fs.copyFileSync(WEBVIEW_PATH, backupPath)
        console.log("[INFO] 备份已创建:", backupPath)
    }

    // 查找 Vdo 函数（DeepSeek UI 组件）
    const vdoIdx = content.indexOf("const Vdo=")
    if (vdoIdx < 0) {
        console.error("[ERROR] 未找到 Vdo 函数（DeepSeek UI 组件）")
        return false
    }
    console.log("[INFO] 找到 Vdo 函数位置:", vdoIdx)

    // 检查当前缓存槽数量
    const cacheMatch = content.substring(vdoIdx, vdoIdx + 200).match(/be\.c\((\d+)\)/)
    if (!cacheMatch) {
        console.error("[ERROR] 未找到 be.c() 缓存槽")
        return false
    }
    const currentSlots = parseInt(cacheMatch[1])
    console.log("[INFO] 当前缓存槽数:", currentSlots)

    // 我们需要添加 2 个新输入框（Context Window, Max Output Tokens）
    // 每个输入框需要约 3 个缓存槽
    const newSlots = currentSlots + 6
    console.log("[INFO] 新缓存槽数:", newSlots)

    // 找到 Vdo 函数的返回语句
    // 当前返回: c.jsxs(c.Fragment,{children:[m,_,C,R,M]})
    // 我们需要找到这个模式并添加新的输入框
    const returnPattern = "c.jsxs(c.Fragment,{children:[m,_,C,R,M]})"
    const returnIdx = content.indexOf(returnPattern, vdoIdx)
    if (returnIdx < 0) {
        console.error("[ERROR] 未找到 Vdo 返回语句")
        console.log("[INFO] 尝试搜索替代模式...")
        // 尝试搜索更宽松的模式
        const altPattern = content.substring(vdoIdx, vdoIdx + 5000)
        const fragMatch = altPattern.match(/c\.jsxs\(c\.Fragment,\{children:\[([^\]]+)\]\}/)
        if (fragMatch) {
            console.log("[INFO] 找到 Fragment children:", fragMatch[1])
        }
        return false
    }
    console.log("[INFO] 找到返回语句位置:", returnIdx)

    // 找到返回语句之前的最后一个缓存槽赋值
    // 当前: e[33]=T):T=e[33],T}
    // 我们需要在 T 赋值之后、return T 之前插入新的输入框代码

    // 策略：
    // 1. 修改 be.c(34) -> be.c(40)
    // 2. 在 return 之前添加 Context Window 和 Max Output Tokens 输入框
    // 3. 修改 Fragment children 数组

    // Step 1: 修改缓存槽数
    const oldCache = `be.c(${currentSlots})`
    const newCache = `be.c(${newSlots})`
    
    // 只替换 Vdo 函数中的 be.c
    const vdoEnd = content.indexOf(",Hdo=", vdoIdx)
    if (vdoEnd < 0) {
        console.error("[ERROR] 未找到 Vdo 函数结束位置（Hdo）")
        return false
    }

    let vdoCode = content.substring(vdoIdx, vdoEnd)
    
    // 替换缓存槽数
    vdoCode = vdoCode.replace(oldCache, newCache)

    // Step 2: 在 T 赋值之后添加新输入框
    // 找到: e[28]!==M||e[29]!==m||e[30]!==_||e[31]!==C||e[32]!==R?(T=c.jsxs(c.Fragment,{children:[m,_,C,R,M]}),e[28]=M,e[29]=m,e[30]=_,e[31]=C,e[32]=R,e[33]=T):T=e[33],T}
    
    // 我们需要：
    // a. 添加 Context Window 输入框变量 (CW)
    // b. 添加 Max Output Tokens 输入框变量 (MO)
    // c. 修改 Fragment children 为 [m,_,C,CW,MO,R,M]

    // 在 "let M;" 之前添加新变量
    const letMIdx = vdoCode.lastIndexOf("let M;")
    if (letMIdx < 0) {
        console.error("[ERROR] 未找到 'let M;'")
        return false
    }

    // 构建新的输入框代码
    // Context Window 输入框
    const contextWindowCode = `let CW;e[${currentSlots}]!==(t==null?void 0:t.deepSeekContextWindow)||e[${currentSlots+1}]!==s?(CW=c.jsx(Qt,{value:String((t==null?void 0:t.deepSeekContextWindow)||""),onInput:s("deepSeekContextWindow",(x)=>{const v=parseInt(x.target.value);return isNaN(v)?void 0:v}),placeholder:"128000",className:"w-full",children:c.jsx("label",{className:"block font-medium mb-1 mt-2",children:"Context Window (Tokens)"})}),e[${currentSlots}]=t==null?void 0:t.deepSeekContextWindow,e[${currentSlots+1}]=s,e[${currentSlots+2}]=CW):CW=e[${currentSlots+2}];`

    // Max Output Tokens 输入框
    const maxOutputCode = `let MO;e[${currentSlots+3}]!==(t==null?void 0:t.deepSeekMaxOutputTokens)||e[${currentSlots+4}]!==s?(MO=c.jsx(Qt,{value:String((t==null?void 0:t.deepSeekMaxOutputTokens)||""),onInput:s("deepSeekMaxOutputTokens",(x)=>{const v=parseInt(x.target.value);return isNaN(v)?void 0:v}),placeholder:"8192",className:"w-full",children:c.jsx("label",{className:"block font-medium mb-1 mt-2",children:"Max Output Tokens"})}),e[${currentSlots+3}]=t==null?void 0:t.deepSeekMaxOutputTokens,e[${currentSlots+4}]=s,e[${currentSlots+5}]=MO):MO=e[${currentSlots+5}];`

    // 在 "let M;" 之前插入新代码
    vdoCode = vdoCode.substring(0, letMIdx) + contextWindowCode + maxOutputCode + vdoCode.substring(letMIdx)

    // Step 3: 修改 Fragment children 数组
    // 原始: children:[m,_,C,R,M]
    // 新的: children:[m,_,C,CW,MO,R,M]
    vdoCode = vdoCode.replace(
        "children:[m,_,C,R,M]",
        "children:[m,_,C,CW,MO,R,M]"
    )

    // Step 4: 更新最后的缓存条件检查
    // 原始: e[28]!==M||e[29]!==m||e[30]!==_||e[31]!==C||e[32]!==R
    // 需要添加 CW 和 MO 的检查
    vdoCode = vdoCode.replace(
        "e[28]!==M||e[29]!==m||e[30]!==_||e[31]!==C||e[32]!==R",
        "e[28]!==M||e[29]!==m||e[30]!==_||e[31]!==C||e[32]!==CW||e[33]!==MO||e[34]!==R"
    )

    // 更新赋值
    vdoCode = vdoCode.replace(
        "e[28]=M,e[29]=m,e[30]=_,e[31]=C,e[32]=R,e[33]=T",
        "e[28]=M,e[29]=m,e[30]=_,e[31]=C,e[32]=CW,e[33]=MO,e[34]=R,e[35]=T"
    )

    // 更新 else 分支
    vdoCode = vdoCode.replace(
        "):T=e[33],T}",
        "):T=e[35],T}"
    )

    // 重新组装
    content = content.substring(0, vdoIdx) + vdoCode + content.substring(vdoEnd)

    // Step 5: 修复 webview 中 DeepSeek 的模型信息查找（进度条 bug）
    // 原始: case"deepseek":{const x=e.apiModelId??s,v=WW[x];return{id:x,info:v}}
    // 问题: WW 只有 deepseek-chat 和 deepseek-reasoner，自定义模型 ID 返回 undefined
    // 修复: 当 WW[x] 找不到时，使用默认模型信息并应用自定义 contextWindow/maxTokens
    const deepseekCaseOld = 'case"deepseek":{const x=e.apiModelId??s,v=WW[x];return{id:x,info:v}}'
    const deepseekCaseNew = 'case"deepseek":{const x=e.apiModelId??s;let v=WW[x]||WW[s];if(v){v={...v};if(e.deepSeekContextWindow){v.contextWindow=e.deepSeekContextWindow}if(e.deepSeekMaxOutputTokens){v.maxTokens=e.deepSeekMaxOutputTokens}}return{id:x,info:v}}'
    if (content.includes(deepseekCaseOld)) {
        content = content.replace(deepseekCaseOld, deepseekCaseNew)
        console.log("[INFO] 已修复 webview 中 DeepSeek 模型信息查找（进度条 bug）")
    } else {
        console.log("[WARN] 未找到 webview 中 DeepSeek case 分支")
    }

    // Step 6: 同时修复 webview 中的 DeepSeek schema（添加新字段）
    const webviewSchemaOld = 'deepSeekBaseUrl:ae().optional(),deepSeekApiKey:ae().optional()})'
    const webviewSchemaNew = 'deepSeekBaseUrl:ae().optional(),deepSeekApiKey:ae().optional(),deepSeekContextWindow:De().optional(),deepSeekMaxOutputTokens:De().optional()})'
    if (content.includes(webviewSchemaOld)) {
        content = content.replace(webviewSchemaOld, webviewSchemaNew)
        console.log("[INFO] 已更新 webview 中 DeepSeek schema")
    } else {
        console.log("[WARN] 未找到 webview 中 DeepSeek schema")
    }

    // Step 7: 隐藏 DeepSeek 的 Model Picker 下拉菜单
    // kco 是排除列表，在其中的提供商不显示 Model Picker
    // 把 "deepseek" 加入排除列表，这样我们的 Model ID 文本框就是唯一的模型选择方式
    const kcoOld = 'kco=["openrouter","requesty","unbound","openai","openai-codex","litellm","vercel-ai-gateway","roo","ollama","lmstudio","vscode-lm"]'
    const kcoNew = 'kco=["openrouter","requesty","unbound","openai","openai-codex","litellm","vercel-ai-gateway","roo","ollama","lmstudio","vscode-lm","deepseek"]'
    if (content.includes(kcoOld)) {
        content = content.replace(kcoOld, kcoNew)
        console.log("[INFO] 已将 deepseek 加入 Model Picker 排除列表")
    } else {
        console.log("[WARN] 未找到 kco 排除列表，Model Picker 可能仍然显示")
    }

    // 写入文件
    fs.writeFileSync(WEBVIEW_PATH, content, "utf8")
    console.log("[✓] Webview UI 补丁成功！")
    console.log("    - 添加了 Context Window 输入框")
    console.log("    - 添加了 Max Output Tokens 输入框")
    console.log("    - 隐藏了 Model Picker 下拉菜单（避免与 Model ID 文本框冲突）")
    return true
}

// ============================================================
// Part 2: Patch Extension.js - Make getModel() use custom values
// ============================================================
function patchExtensionJS() {
    console.log("\n" + "=".repeat(60))
    console.log("Part 2: 修补 Extension.js (后端)")
    console.log("=".repeat(60))

    if (!fs.existsSync(EXTENSION_PATH)) {
        console.error("[ERROR] 未找到 extension.js:", EXTENSION_PATH)
        return false
    }

    let content = fs.readFileSync(EXTENSION_PATH, "utf8")

    // 备份
    const backupPath = EXTENSION_PATH + ".bak-deepseek-options"
    if (!fs.existsSync(backupPath)) {
        fs.copyFileSync(EXTENSION_PATH, backupPath)
        console.log("[INFO] 备份已创建:", backupPath)
    }

    // 1. 修改 DeepSeek schema 添加新字段
    // 原始: oir=Lm.extend({deepSeekBaseUrl:K.string().optional(),deepSeekApiKey:K.string().optional()})
    const schemaPattern = 'deepSeekBaseUrl:K.string().optional(),deepSeekApiKey:K.string().optional()})'
    const schemaIdx = content.indexOf(schemaPattern)
    if (schemaIdx < 0) {
        console.error("[ERROR] 未找到 DeepSeek schema 定义")
        return false
    }
    console.log("[INFO] 找到 DeepSeek schema 位置:", schemaIdx)

    // 添加新字段到 schema
    const newSchema = 'deepSeekBaseUrl:K.string().optional(),deepSeekApiKey:K.string().optional(),deepSeekContextWindow:K.number().optional(),deepSeekMaxOutputTokens:K.number().optional()})'
    content = content.substring(0, schemaIdx) + newSchema + content.substring(schemaIdx + schemaPattern.length)
    console.log("[INFO] Schema 已更新")

    // 2. 修改 getModel() 方法
    // 原始: getModel(){let e=this.options.apiModelId??UB,r=Wee[e]||Wee[UB],a=il({format:"openai",modelId:e,model:r,settings:this.options,defaultTemperature:dG});return{id:e,info:r,...a}}
    // 需要在返回之前覆盖 contextWindow 和 maxTokens
    
    const getModelPattern = 'getModel(){let e=this.options.apiModelId??UB,r=Wee[e]||Wee[UB]'
    const getModelIdx = content.indexOf(getModelPattern)
    if (getModelIdx < 0) {
        console.error("[ERROR] 未找到 DeepSeek getModel() 方法")
        return false
    }
    console.log("[INFO] 找到 getModel() 位置:", getModelIdx)

    // 找到 getModel 的完整代码
    const getModelEnd = content.indexOf('}}', getModelIdx + getModelPattern.length)
    if (getModelEnd < 0) {
        console.error("[ERROR] 未找到 getModel() 结束位置")
        return false
    }

    const oldGetModel = content.substring(getModelIdx, getModelEnd + 2)
    console.log("[INFO] 原始 getModel():", oldGetModel.substring(0, 200) + "...")

    // 构建新的 getModel 方法
    // 关键改动：
    // - 如果用户设置了 deepSeekContextWindow，覆盖模型的 contextWindow
    // - 如果用户设置了 deepSeekMaxOutputTokens，覆盖模型的 maxTokens
    const newGetModel = `getModel(){let e=this.options.apiModelId??UB,r={...(Wee[e]||Wee[UB])};if(this.options.deepSeekContextWindow){r.contextWindow=this.options.deepSeekContextWindow}if(this.options.deepSeekMaxOutputTokens){r.maxTokens=this.options.deepSeekMaxOutputTokens}let a=il({format:"openai",modelId:e,model:r,settings:this.options,defaultTemperature:dG});return{id:e,info:r,...a}}`

    content = content.substring(0, getModelIdx) + newGetModel + content.substring(getModelIdx + oldGetModel.length)
    console.log("[INFO] getModel() 已更新")

    // 写入文件
    fs.writeFileSync(EXTENSION_PATH, content, "utf8")
    console.log("[✓] Extension.js 补丁成功！")
    console.log("    - Schema 添加了 deepSeekContextWindow 和 deepSeekMaxOutputTokens")
    console.log("    - getModel() 现在支持自定义上下文窗口和最大输出 Token")
    return true
}

// ============================================================
// Main
// ============================================================
function main() {
    console.log("=".repeat(60))
    console.log("Roo Code DeepSeek 高级选项补丁")
    console.log("=".repeat(60))

    const uiResult = patchWebviewUI()
    const backendResult = patchExtensionJS()

    console.log("\n" + "=".repeat(60))
    console.log("补丁结果:")
    console.log("  UI 补丁:", uiResult ? "✓ 成功" : "✗ 失败")
    console.log("  后端补丁:", backendResult ? "✓ 成功" : "✗ 失败")
    console.log("=".repeat(60))

    if (uiResult && backendResult) {
        console.log("\n[✓] 所有补丁已成功应用！")
        console.log("请重启 VS Code 以使更改生效。")
        console.log("\n新增选项说明：")
        console.log("  - Context Window: 设置上下文窗口大小（默认 128000，V4 支持最大 1000000）")
        console.log("  - Max Output Tokens: 设置最大输出 Token 数（默认 8192）")
    } else {
        console.log("\n[!] 部分补丁失败，请检查上方错误信息")
        process.exit(1)
    }
}

main()
