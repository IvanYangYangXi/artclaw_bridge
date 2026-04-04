# Crash Rules

> 导致崩溃、数据丢失或严重错误的已知问题。每次 briefing 必读。

- [UE] TEXT()/LOCTEXT() 宏不能嵌 UTF-8 emoji 字节序列，Windows wchar_t 会乱码
- [UE] Slate 弹窗必须用 AddWindowAsNativeChild，否则弹窗跑到主界面后面
- [Maya] FBX 导入路径含中文字符会崩溃，先转 ASCII 路径
- [Maya] 中文版有两个安装目录 scripts/ 和 zh_CN/scripts/，都必须同步写入
- [Windows] bat 文件必须 CRLF 换行，LF 会导致 cmd.exe 解析错位
- [Windows] bat echo 行禁止 > → -> 字符，会被当成文件重定向
- [Windows] Python CLI 要加 UTF-8 stdout reconfigure，否则 emoji 输出崩溃
- [Python] importlib.reload 后已创建实例的方法不自动更新，需 types.MethodType 手动绑定
- [UE] Gateway /new 命令会关闭 WebSocket(1000 OK)，不能通过 bridge RPC 发 /new
- [UE] _connect_loop 断连时必须通知 _wait_for_final，否则卡 300s 超时
- [UE] /cancel 必须双端联动: C++ 清 UI + 停 poll + Python cancel 释放 wait
- [UE] send_chat_async 新请求前必须先 cancel 旧请求，用 request_id 防竞态
