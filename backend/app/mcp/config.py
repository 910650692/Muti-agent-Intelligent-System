"""MCP Servers 配置加载器"""
import json
import os
from typing import Dict, Any


def load_mcp_config() -> Dict[str, Any]:
    """
    从 JSON 文件加载 MCP Servers 配置

    Returns:
        MCP Servers 配置字典
    """
    config_path = os.path.join(os.path.dirname(__file__), "mcp_config.json")

    if not os.path.exists(config_path):
        print(f"[MCP Config] 警告: 配置文件不存在: {config_path}")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        # 获取 mcpServers 部分
        mcp_servers = config.get("mcpServers", {})

        # 处理环境变量替换
        processed_servers = {}
        for name, server_config in mcp_servers.items():
            processed_config = server_config.copy()

            # 处理 env 中的环境变量占位符
            if "env" in processed_config and processed_config["env"]:
                processed_env = {}
                for key, value in processed_config["env"].items():
                    # 替换 ${VAR_NAME} 格式的环境变量
                    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                        env_var_name = value[2:-1]  # 去掉 ${ 和 }
                        processed_env[key] = os.getenv(env_var_name, "")
                        if not processed_env[key]:
                            print(f"[MCP Config] 警告: 环境变量 {env_var_name} 未设置 (Server: {name})")
                    else:
                        processed_env[key] = value
                processed_config["env"] = processed_env

            processed_servers[name] = processed_config

        print(f"[MCP Config] 成功加载配置，共 {len(processed_servers)} 个 Server")
        return processed_servers

    except json.JSONDecodeError as e:
        print(f"[MCP Config] 错误: JSON 格式错误: {e}")
        return {}
    except Exception as e:
        print(f"[MCP Config] 错误: 加载配置失败: {e}")
        return {}


def get_enabled_servers() -> Dict[str, Any]:
    """
    获取所有启用的 MCP Servers

    Returns:
        启用的 MCP Servers 配置字典
    """
    all_servers = load_mcp_config()

    enabled_servers = {
        name: config
        for name, config in all_servers.items()
        if config.get("enabled", True)  # 默认启用
    }

    print(f"[MCP Config] 已启用 {len(enabled_servers)} 个 Server:")
    for name, config in enabled_servers.items():
        desc = config.get("description", "无描述")
        print(f"  - {name}: {desc}")

    return enabled_servers


def save_mcp_config(servers: Dict[str, Any]) -> bool:
    """
    保存 MCP Servers 配置到 JSON 文件

    Args:
        servers: MCP Servers 配置字典

    Returns:
        是否保存成功
    """
    config_path = os.path.join(os.path.dirname(__file__), "mcp_config.json")

    try:
        # 读取现有配置（保留注释和示例）
        existing_config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                existing_config = json.load(f)

        # 更新 mcpServers 部分
        existing_config["mcpServers"] = servers

        # 写回文件（带缩进，便于阅读）
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, indent=2, ensure_ascii=False)

        print(f"[MCP Config] 配置已保存到: {config_path}")
        return True

    except Exception as e:
        print(f"[MCP Config] 保存配置失败: {e}")
        return False


# 向后兼容：导出为 MCP_SERVERS
MCP_SERVERS = load_mcp_config()
