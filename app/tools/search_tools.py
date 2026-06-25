# 后端 联网搜索工具 — Tavily API + DuckDuckGo 兜底 + 天气
import urllib.request
import urllib.parse
import json
import os
from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# ===== 后端 代理配置 =====
# 后端 国内服务器访问 Tavily / DuckDuckGo / wttr.in 需要代理
# 后端 在 .env 中设置 HTTP_PROXY 和 HTTPS_PROXY 即可（如 http://127.0.0.1:7890）
_PROXIES = {}
if settings.http_proxy:
    _PROXIES["http"] = settings.http_proxy
if settings.https_proxy:
    _PROXIES["https"] = settings.https_proxy
# 后端 urllib 用 ProxyHandler + build_opener（天气查询用）
_proxy_handler = urllib.request.ProxyHandler(_PROXIES) if _PROXIES else None
_proxy_opener = urllib.request.build_opener(_proxy_handler) if _proxy_handler else None


def search_internet(query: str, max_results: int = 5) -> str:
    """后端 联网搜索 — Tavily 优先，不可用则降级 DDG，均支持代理"""
    # 后端 设置代理环境变量（DDGS 库通过环境变量读取代理）
    if _PROXIES:
        for proto, proxy_url in _PROXIES.items():
            os.environ[proto + "_proxy"] = proxy_url

    # ===== Tavily 优先（AI 专用搜索，结果质量高，需 API Key）=====
    if settings.tavily_api_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=settings.tavily_api_key)
            response = client.search(
                query=query, max_results=max_results,
                search_depth="advanced", days=30,
            )
            results = response.get("results", [])
            if results:
                lines = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "无标题")
                    url = r.get("url", "无链接")
                    content = r.get("content", "无摘要")
                    lines.append(f"{i}. {title}\n   链接: {url}\n   摘要: {content}\n")
                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Tavily 失败，降级 DDG: {str(e)[:80]}")

    # ===== DDG 兜底（免费，无需 API Key，但国内可能被墙需代理）=====
    try:
        from duckduckgo_search import DDGS
        results = []
        # 后端 传入 proxies 参数（新版 ddgs 库支持）
        ddgs_kwargs = {}
        if _PROXIES:
            ddgs_kwargs["proxies"] = _PROXIES
        with DDGS(**ddgs_kwargs) as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
        if not results:
            return f"未找到与「{query}」相关的结果，请检查网络或配置代理（HTTP_PROXY）"
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            url = r.get("href", "无链接")
            content = r.get("body", "无摘要")
            lines.append(f"{i}. {title}\n   链接: {url}\n   摘要: {content}\n")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)[:100]}")
        return f"搜索失败: {str(e)[:200]}。中国大陆可能无法访问 DuckDuckGo，请在 .env 中配置 HTTP_PROXY 代理。"


def fetch_weather(city: str) -> str:
    """后端 查询城市实时天气（wttr.in 免费 API，支持代理）"""
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=zh"
        opener = _proxy_opener or urllib.request.build_opener()
        with opener.open(url, timeout=10) as resp:
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
        logger.warning(f"天气查询失败: {city} - {e}")
        return f"天气查询失败: {str(e)[:200]}"


# 后端 工具 Schema 字典（供 mcp_server.py 注册时取用 parameters，避免重复定义）
SEARCH_TOOL_SCHEMAS = {
    "search_internet": {
        "name": "search_internet",
        "description": "搜索最新信息（优先 Tavily API，自动降级 DuckDuckGo）。查新闻/趋势/数据时必调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "max_results": {"type": "integer", "description": "最多返回条数，默认 5"}
            },
            "required": ["query"]
        }
    },
    "fetch_weather": {
        "name": "fetch_weather",
        "description": "查询指定城市的实时天气信息",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市名称"}},
            "required": ["city"]
        }
    }
}
