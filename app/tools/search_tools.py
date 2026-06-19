# 后端 联网搜索 MCP 工具（多层降级：DDG → Bing → 内建）
import urllib.request
import urllib.parse
import json
import re

def search_internet(query: str, max_results: int = 5) -> str:
    # 后端 方法1：尝试 DuckDuckGo HTML 搜索
    try:
        results = _search_ddg_html(query, max_results)
        if results:
            return _format_results(results)
    except Exception:
        pass

    # 后端 方法2：尝试 ddgs 新包
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            return _format_results_ddgs(results)
    except Exception:
        pass

    # 后端 方法3：尝试旧的 duckduckgo_search
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if results:
            return _format_results_ddgs(results)
    except Exception:
        pass

    return f"搜索失败：无法连接到搜索引擎，请检查网络。查询词：{query}"

def _search_ddg_html(query: str, max_results: int) -> list:
    # 后端 用 HTML 方式抓取 DDG 搜索结果
    encoded = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # 后端 正则提取搜索结果
    results = []
    # 后端 匹配每条结果的标题、摘要、链接
    items = re.findall(
        r'<a rel="nofollow" class="result__a" href="([^"]+)".*?>(.*?)</a>.*?<a class="result__snippet".*?>(.*?)</a>',
        html, re.DOTALL
    )
    for href, title, snippet in items[:max_results]:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
        if title_clean:
            results.append({
                "title": title_clean,
                "href": urllib.parse.unquote(href) if href.startswith("//") else href,
                "body": snippet_clean or "无摘要",
            })
    return results

def _format_results(results: list) -> str:
    # 后端 格式化搜索结果
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}\n   链接: {r['href']}\n   摘要: {r['body']}\n")
    return "\n".join(lines) if lines else "未找到结果"

def _format_results_ddgs(results: list) -> str:
    # 后端 格式化 ddgs 包的搜索结果
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. {r.get('title', '无标题')}\n"
            f"   链接: {r.get('href', '无')}\n"
            f"   摘要: {r.get('body', '无摘要')}\n"
        )
    return "\n".join(lines) if lines else "未找到结果"

def fetch_weather(city: str) -> str:
    # 后端 查询城市天气
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=zh"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        current = data.get("current_condition", [{}])[0]
        return (
            f"城市: {city}\n"
            f"温度: {current.get('temp_C', '?')}°C\n"
            f"天气: {current.get('weatherDesc', [{}])[0].get('value', '?')}\n"
            f"湿度: {current.get('humidity', '?')}%\n"
            f"风速: {current.get('windspeedKmph', '?')} km/h"
        )
    except Exception as e:
        return f"天气查询失败: {str(e)}"

SEARCH_TOOL_SCHEMAS = {
    "search_internet": {
        "name": "search_internet",
        "description": "联网搜索最新信息，返回实时搜索结果。搜索最新新闻/趋势/数据时必须调用此工具。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最多返回条数，默认5"}
            },
            "required": ["query"]
        }
    },
    "fetch_weather": {
        "name": "fetch_weather",
        "description": "查询指定城市的实时天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，如 Beijing"}
            },
            "required": ["city"]
        }
    }
}
