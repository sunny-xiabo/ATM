"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_case_writer_test.py
# @Date: 2025/8/28 15:26
"""
"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_case_writer_test.py
# @Date: 2025/8/28 14:44
"""

import os
import json
import logging
from dotenv import load_dotenv
from src.agents.test_case_writer import TestCaseWriterAgent

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


def test_generate_feature_test_cases():
    """测试为特定功能点生成测试用例的功能"""

    # 初始化测试用例编写者代理
    writer = TestCaseWriterAgent()

    # 功能点的测试覆盖矩阵
    feature = ""
    feature_items = [
        {
            "feature": "",
            "test_type": "功能测试"
        }
    ]

    # 模拟优先级定义
    priorities = [
        {"level": "P0", "description": "核心功能，必须测试"}
    ]

    # 模拟测试方法
    test_approach = {
        "测试方法": ["黑盒测试", "功能测试"]
    }
    # 调用测试用例生成方法
    test_cases = writer._generate_feature_test_cases(
        feature=feature,
        feature_items=feature_items,
        priorities=priorities,
        test_approach=test_approach
    )

    # 输出结果
    logger.info(f"生成的测试用例数量: {len(test_cases)}")
    if test_cases:
        logger.info(f"第一个测试用例: {json.dumps(test_cases[0], ensure_ascii=False, indent=2)}")
    else:
        logger.error("未能生成任何测试用例")

    return test_cases


def main():
    logger.info("开始测试测试用例生成功能")
    test_cases = test_generate_feature_test_cases()

    if test_cases:
        logger.info("测试成功: 成功生成测试用例")
    else:
        logger.error("测试失败: 未能生成测试用例")


if __name__ == "__main__":
    main()

