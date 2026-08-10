#!/usr/bin/env python3
"""LLM Wiki 交互式对话框。

自动启动 llm-wiki-server，通过 MCP 协议对话。
支持知识库查询、读取、写入、编译素材，全部对话式完成。
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

# ── 颜色工具 ─────────────────────────────────────────────
class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    CLEAR_LINE = "\033[K"


def c(text: str, *codes: str) -> str:
    return "".join(codes) + text + Color.RESET


# ── MCP 客户端 ───────────────────────────────────────────
class MCPClient:
    """通过 stdio 协议连接 llm-wiki-server。"""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._buf = ""

    def start(self):
        """启动 llm-wiki-server 子进程。"""
        print(c("  🚀 正在启动 LLM Wiki 服务...", Color.DIM), end="", flush=True)
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        # 握手初始化
        self._rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "llm-wiki-chat", "version": "1.0"},
        })
        self._proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        self._proc.stdin.flush()
        print(c(" ✅", Color.GREEN))

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def _rpc(self, method: str, params: dict, id: int = 1) -> dict:
        """发送 RPC 请求并等待响应。"""
        req = json.dumps({
            "jsonrpc": "2.0", "id": id,
            "method": method, "params": params,
        })
        self._proc.stdin.write(req + "\n")
        self._proc.stdin.flush()
        return self._read_response()

    def _read_response(self) -> dict:
        """读取一行 JSON 响应。"""
        line = self._proc.stdout.readline()
        while line:
            line = line.strip()
            if line:
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
            line = self._proc.stdout.readline()
        return {}

    def call(self, tool: str, args: dict) -> str:
        """调用 MCP 工具，返回结果文本。"""
        resp = self._rpc("tools/call", {"name": tool, "arguments": args})
        if "error" in resp:
            return c(f"❌ 错误: {resp['error'].get('message', '未知错误')}", Color.RED)
        content = resp.get("result", {}).get("content", [])
        return content[0]["text"] if content else "(空结果)"

    def list_tools(self) -> list[dict]:
        resp = self._rpc("tools/list", {})
        return resp.get("result", {}).get("tools", [])


# ── 对话引擎 ─────────────────────────────────────────────
class ChatEngine:
    """理解用户意图，调用合适的 MCP 工具。"""

    def __init__(self, client: MCPClient, use_llm: bool = False):
        self.client = client
        self.use_llm = use_llm

    def _llm_chat(self, system: str, user: str) -> str:
        """调用 LLM API 进行对话。返回回答文本。"""
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return c("⚠️  未设置 OPENAI_API_KEY，无法使用 LLM 回答", Color.YELLOW)

        base_url = os.getenv("OPENAI_BASE_URL", "")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url

        model = os.getenv("CHAT_MODEL", "deepseek-chat")
        client = OpenAI(**kwargs)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )
        return resp.choices[0].message.content or "（空回复）"

    async def answer(self, user_input: str) -> str:
        """根据用户输入，自动选择并调用工具。"""
        text = user_input.strip()
        if not text:
            return ""

        # ── 意图识别规则 ──
        # 查询类
        if any(kw in text for kw in ["查一下", "查询", "搜索", "搜一下", "什么是", "是什么", "说说", "告诉我", "？", "?"]):
            return self._handle_query(text)

        # 读取类
        if any(kw in text for kw in ["读一下", "看看", "打开", "显示", "显示内容"]):
            return self._handle_read(text)

        # 写入类
        if any(kw in text for kw in ["记一下", "记录", "保存", "存一下", "写入", "新建"]):
            return self._handle_write(text)

        # 编译类
        if any(kw in text for kw in ["编译", "提取", "ingest"]):
            return self._handle_ingest(text)

        # 默认：当查询处理
        return self._handle_query(text)

    def _handle_query(self, text: str) -> str:
        """处理查询类请求。"""
        # 提取问题：去掉前缀词
        q = text
        for prefix in ["查一下", "查询", "搜一下", "搜索", "什么是", "是什么", "说说", "告诉我"]:
            q = q.replace(prefix, "").strip()
        q = q.strip("?？，,。.")
        if not q:
            q = text

        result = self.client.call("query", {"question": q})
        if result == "（无检索结果）":
            return c(f"📭 知识库中还没有关于「{q}」的内容。", Color.YELLOW) + \
                   "\n  你可以说「记一下 ...」来添加，或者换个关键词试试。"

        # ── LLM 模式：检索 + 生成 ──
        if self.use_llm:
            # 截取检索结果前 2000 字作为上下文
            context = result[:2000]
            system = (
                "你是个人知识库助手。你基于检索到的 Wiki 片段回答用户问题。"
                "如果片段信息不足，坦白说不知道。不要编造。引用片段时注明来源页面名。"
            )
            user_prompt = (
                f"## 检索到的知识库片段\n\n{context}\n\n"
                f"## 用户问题\n\n{q}"
            )
            llm_reply = self._llm_chat(system, user_prompt)
            # 附上原始片段供参考
            return c(f"💬 {llm_reply}", Color.GREEN) + "\n\n" + \
                   c("── 检索来源 ──", Color.DIM) + "\n" + \
                   "\n".join(result.split("\n")[:3])

        # ── 纯检索模式：直接返回片段 ──
        lines = result.split("\n---\n")
        parts = []
        for i, block in enumerate(lines):
            block = block.strip()
            if not block:
                continue
            # 提取页面名
            if block.startswith("["):
                end = block.find("]")
                page = block[1:end]
                content = block[end+1:].strip()
                parts.append(f"{c(f'📄 {page}', Color.CYAN, Color.BOLD)}\n  {content[:200]}")
            else:
                parts.append(f"  {block[:200]}")
        if len(lines) > 3:
            parts.append(c(f"  ... 还有 {len(lines)-3} 条相关结果", Color.DIM))
        return "\n".join(parts) if parts else result

    def _handle_read(self, text: str) -> str:
        """处理读取类请求。"""
        # 提取页面名
        for kw in ["读一下", "看看", "打开", "显示", "显示内容"]:
            text = text.replace(kw, "").strip()
        page = text.strip("《》「」\"'").strip()
        if not page:
            return c("❓ 你想读哪个页面？例如「读一下 LLM_Wiki」", Color.YELLOW)
        try:
            result = self.client.call("read_wiki", {"page": page})
            # 只显示正文部分，frontmatter 精简
            lines = result.split("\n")
            if lines and lines[0].startswith("---"):
                # 找到正文开始
                body_start = 0
                for i, l in enumerate(lines):
                    if l == "---" and i > 0:
                        body_start = i + 1
                        break
                # 提取 frontmatter 关键信息
                fm_info = []
                for l in lines[1:body_start-1]:
                    for key in ["title:", "type:", "tags:", "created:", "updated:"]:
                        if l.strip().startswith(key):
                            fm_info.append(l.strip())
                            break
                header = c(f"📖 {page}", Color.CYAN, Color.BOLD) + "\n"
                header += c(" | ".join(fm_info), Color.DIM) + "\n"
                body_lines = lines[body_start:]
                body = "\n".join(body_lines)
                # 限制显示长度
                if len(body) > 2000:
                    body = body[:2000] + c("\n\n... (内容过长，已截断)", Color.DIM)
                return header + body
            return result
        except Exception as e:
            return c(f"❌ 读取失败: {e}", Color.RED)

    def _handle_write(self, text: str) -> str:
        """处理写入类请求。"""
        # 提取标题：通常在"记一下/记录/保存"之后
        title = text
        for kw in ["记一下", "记一下 ", "记录", "记录 ", "保存", "保存 ", "存一下", "写入", "新建"]:
            title = title.replace(kw, "").strip()
        # 去掉常见后缀
        title = title.strip("《》「」\"'").strip()
        if not title or len(title) < 2:
            return c("❓ 你想记什么？例如「记一下 Python 异步编程」", Color.YELLOW)
        
        # 简洁模式：直接创建页面
        safe_title = title.replace(" ", "_")
        body = f"# {title}\n\n（待完善）\n"
        result = self.client.call("write_wiki", {
            "title": safe_title,
            "body": body,
            "page_type": "concept",
            "tags": "",
        })
        return c(f"✅ 已创建页面「{safe_title}」", Color.GREEN) + "\n" + \
               c(f"  你说「写一下 {safe_title} 的内容是 ...」来补充内容", Color.DIM)

    def _handle_ingest(self, text: str) -> str:
        """处理编译类请求。"""
        # 提取文件路径
        for kw in ["编译", "提取", "ingest"]:
            text = text.replace(kw, "").strip()
        path = text.strip().strip("'\"")
        if not path or not Path(path).exists():
            # 自动补全路径
            for test_path in [path, f"data/raw/{path}", f"data/raw/{path}.md"]:
                if Path(test_path).exists():
                    path = test_path
                    break
            else:
                files = list(Path("data/raw").glob("*.md"))
                if files:
                    hint = "\n".join(f"  📄 {f}" for f in files)
                    return c(f"📂 可编译的素材:\n{hint}\n\n说「编译 文件名」来编译", Color.YELLOW)
                else:
                    return c("📭 data/raw/ 目录下没有素材文件，先放一些 .md 进去再编译", Color.YELLOW)
        try:
            result = self.client.call("ingest", {"raw_path": path})
            return c(f"✅ {result}", Color.GREEN)
        except Exception as e:
            return c(f"❌ 编译失败: {e}", Color.RED)


# ── 交互式 UI ────────────────────────────────────────────
def clear_screen():
    os.system("clear" if os.name == "posix" else "cls")


def print_status(use_llm: bool = False):
    """打印当前状态信息。"""
    from app.config import settings

    embed_mode = settings.embed_provider
    embed_desc = {
        "api": f"API ({settings.embed_model})",
        "local": "本地 TF-IDF",
        "off": "关闭（仅 BM25）",
    }.get(embed_mode, embed_mode)
    retrieval = "向量 + BM25 + RRF" if settings.embed_enabled else "BM25 + 链接扩展"
    if settings.embed_enabled:
        retrieval += " + 链接扩展"
    llm_mode = c("LLM 回答", Color.GREEN, Color.BOLD) if use_llm else c("纯检索", Color.DIM)

    print(f"  {c('📡', Color.DIM)} 检索:   {c(retrieval, Color.CYAN)}")
    print(f"  {c('🎯', Color.DIM)} Embed:  {c(embed_desc, Color.CYAN)}")
    print(f"  {c('🤖', Color.DIM)} 回答:   {llm_mode}")
    wiki_count = len(list(Path("data/wiki").glob("*.md")))
    print(f"  {c('📚', Color.DIM)} Wiki:   {c(f'{wiki_count} 页', Color.CYAN)}")
    print()


def print_banner(use_llm: bool = False):
    banner = f"""
{Color.CYAN}{Color.BOLD}
  ╔══════════════════════════════════════════════╗
  ║       🧠  LLM Wiki  —  个人知识库对话        ║
  ╚══════════════════════════════════════════════╝
{Color.RESET}
"""
    print(banner)
    print_status(use_llm)
    print(c("  你可以这样说：", Color.DIM))
    examples = [
        ("查一下", "Agent 是什么"),
        ("读一下", "LLM_Wiki"),
        ("记一下", "Python 异步编程"),
        ("编译", "data/raw/sample_agent_notes.md"),
    ]
    for action, example in examples:
        print(f"    {c(action, Color.GREEN)} {c(example, Color.DIM)}")
    print()


def print_help(use_llm: bool = False):
    llm_hint = c("开", Color.GREEN) if use_llm else c("关", Color.DIM)
    help_text = f"""
{c("可用命令:", Color.BOLD)}
  {c("/help", Color.MAGENTA)}     显示此帮助
  {c("/tools", Color.MAGENTA)}    查看可用 MCP 工具
  {c("/pages", Color.MAGENTA)}    列出知识库所有页面
  {c("/rebuild", Color.MAGENTA)}  重建索引
  {c("/llm", Color.MAGENTA)}      切换 LLM 回答（当前{llm_hint}）
  {c("/clear", Color.MAGENTA)}    清屏
  {c("/exit", Color.MAGENTA)}     退出

{c("常用对话:", Color.BOLD)}
  {c("查一下 <话题>", Color.GREEN)}    — 搜索知识库
  {c("读一下 <页面>", Color.GREEN)}    — 读取页面全文
  {c("记一下 <标题>", Color.GREEN)}    — 新建空白页面
  {c("编译 <文件>", Color.GREEN)}      — 编译 raw 素材为 Wiki
"""
    print(help_text)


def print_bot_msg(text: str):
    """打印 AI 回复。"""
    print()
    for line in text.split("\n"):
        print(f"  {line}")
    print()


def get_user_input() -> str:
    """获取用户输入，支持多行（空行结束）和历史导航。"""
    try:
        text = input(f"\n{Color.GREEN}  you> {Color.RESET}").strip()
        return text
    except (EOFError, KeyboardInterrupt):
        return "/exit"


# ── 主循环 ───────────────────────────────────────────────
async def main():
    import argparse

    # 加载 .env 环境变量（让 LLM 调用能读到 OPENAI_API_KEY）
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="LLM Wiki 交互式对话框")
    parser.add_argument("--llm", action="store_true", help="启用 LLM 回答模式")
    args = parser.parse_args()

    use_llm = args.llm
    clear_screen()

    client = MCPClient()
    try:
        client.start()
    except Exception as e:
        print(c(f"❌ 启动服务失败: {e}", Color.RED))
        print(c("  请确认已安装依赖: pip install fastmcp openai pyyaml python-dotenv", Color.DIM))
        sys.exit(1)

    engine = ChatEngine(client, use_llm=use_llm)
    print_banner(use_llm)

    # 自动重建索引
    if not Path("data/index.json").exists():
        print(c("  ⚡ 首次使用，自动重建索引...", Color.DIM))
        client.call("rebuild_index", {})
        print(c("  ✅ 索引已就绪", Color.GREEN))
        print()

    while True:
        try:
            user_input = get_user_input()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # ── 命令处理 ──
        if user_input == "/exit":
            break
        elif user_input == "/help":
            print_help(use_llm)
            continue
        elif user_input == "/tools":
            tools = client.list_tools()
            print(c(f"\n  可用工具 ({len(tools)}):", Color.BOLD))
            for t in tools:
                print(f"    🛠️  {c(t['name'], Color.CYAN)} — {t.get('description', '')}")
            print()
            continue
        elif user_input == "/pages":
            wiki_dir = Path("data/wiki")
            if wiki_dir.exists():
                pages = sorted(p.stem for p in wiki_dir.glob("*.md"))
                if pages:
                    print(c(f"\n  📚 知识库 ({len(pages)} 页):", Color.BOLD))
                    for p in pages:
                        print(f"    📄 {p}")
                else:
                    print(c("\n  📭 知识库为空", Color.YELLOW))
            else:
                print(c("\n  📭 data/wiki/ 目录不存在", Color.YELLOW))
            print()
            continue
        elif user_input == "/llm":
            use_llm = not use_llm
            engine.use_llm = use_llm
            print(c(f"\n  🤖 LLM 回答已{'开启' if use_llm else '关闭'}", Color.GREEN if use_llm else Color.DIM))
            print()
            continue
        elif user_input == "/rebuild":
            print(c("  🔄 重建索引中...", Color.DIM))
            result = client.call("rebuild_index", {})
            print(c(f"  ✅ {result}", Color.GREEN))
            continue
        elif user_input == "/clear":
            clear_screen()
            print_banner(use_llm)
            continue

        # ── 对话处理 ──
        print(c("  🤖 思考中...", Color.DIM))
        response = await engine.answer(user_input)
        print_bot_msg(response)

    # 退出
    client.stop()
    print(c("\n  👋 拜拜！知识库已保存。\n", Color.DIM))


if __name__ == "__main__":
    asyncio.run(main())
