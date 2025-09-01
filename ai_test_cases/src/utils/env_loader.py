"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: env_loader.py
# @Date: 2025/8/26 14:49
"""

from dotenv import load_dotenv
import os

def load_env_variables():
    """
    加载环境变量
    :return: dict
            {
                "BASE_URL": 基础URL,
                "LLM_KEY": API密钥,
                "LLM_MODEL": 模型版本
            }
    """

    # 加载.env文件
    load_dotenv()

    # 获取环境变量
    env_vars = {
        "BASE_URL": os.getenv("BASE_URL"),
        "LLM_KEY": os.getenv("LLM_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL")
    }

    # 检查是否所有必要的环境变量都已设置
    missing_vars = [key for key, value in env_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"缺少必要的环境变量: {', '.join(missing_vars)}")
    return env_vars

if __name__ == "__main__":
    missing_vars = load_env_variables()
    print(missing_vars)