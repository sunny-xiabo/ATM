"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_improve_with_llm_direct.py
# @Date: 2025/8/28 15:48
"""

import json
import os
import logging
import sys

from dotenv import load_dotenv


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入TestCaseWriterAgent
from src.agents.test_case_writer import TestCaseWriterAgent

def main():
    """使用test_case_writer_result.json测试_improve_with_llm函数"""
    try:
        # 初始化测试用例编写者代理
        writer = TestCaseWriterAgent()

        # 加载测试用例数据
        test_cases_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       'agent_results', 'test_case_writer_result.json')

        logger.info(f"加载测试用例数据: {test_cases_path}")
        with open(test_cases_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            test_cases = test_data.get('test_cases', [])

        # 确保至少有一些测试用例
        if len(test_cases) == 0:
            logger.error("测试数据中没有测试用例")
            return

        logger.info(f"成功加载 {len(test_cases)} 个测试用例")

        # 准备质量审查反馈
        feedback = """质量审查反馈：
            1. 完整性：
            - 部分测试用例缺少详细的前置条件
            - 有些测试用例的步骤描述不够详细

            2. 清晰度：
            - 测试用例标题应更具体，明确测试目标
            - 步骤描述应更加清晰，避免歧义

            3. 可执行性：
            - 确保每个步骤都有对应的预期结果
            - 添加具体的测试数据示例

            4. 边界情况：
            - 缺少对边界值的测试
            - 应考虑极端情况下的系统行为

            5. 错误场景：
            - 缺少对错误处理的测试
            - 应添加异常路径测试"""

        # 使用前5个测试用例进行测试，避免处理过多数据
        test_sample = test_cases[:5]
        logger.info(f"使用前 {len(test_sample)} 个测试用例进行测试")

        # 调用_improve_with_llm函数
        logger.info("开始调用_improve_with_llm函数...")
        improved_cases = writer._improve_with_llm(test_sample, feedback)

        # 检查结果
        if not improved_cases:
            logger.warning("_improve_with_llm函数返回空结果")
            return

        logger.info(f"成功获取 {len(improved_cases)} 个改进后的测试用例")

        # 输出改进前后的对比
        logger.info("\n改进前后的测试用例对比:")
        for i, (original, improved) in enumerate(zip(test_sample, improved_cases[:len(test_sample)])):
            logger.info(f"\n测试用例 {i + 1}:")
            logger.info(f"原始ID: {original.get('id', 'N/A')} -> 改进后ID: {improved.get('id', 'N/A')}")
            logger.info(f"原始标题: {original.get('title', 'N/A')}")
            logger.info(f"改进后标题: {improved.get('title', 'N/A')}")

            # 比较前置条件数量
            orig_precond = original.get('preconditions', [])
            impr_precond = improved.get('preconditions', [])
            logger.info(f"前置条件: {len(orig_precond)} -> {len(impr_precond)}")

            # 比较步骤数量
            orig_steps = original.get('steps', [])
            impr_steps = improved.get('steps', [])
            logger.info(f"步骤数量: {len(orig_steps)} -> {len(impr_steps)}")

            # 比较预期结果数量
            orig_results = original.get('expected_results', [])
            impr_results = improved.get('expected_results', [])
            logger.info(f"预期结果数量: {len(orig_results)} -> {len(impr_results)}")

        # 检查是否有新增的测试用例
        if len(improved_cases) > len(test_sample):
            logger.info(f"\n新增了 {len(improved_cases) - len(test_sample)} 个测试用例:")
            for i, new_case in enumerate(improved_cases[len(test_sample):]):
                logger.info(f"新增测试用例 {i + 1}: {new_case.get('id', 'N/A')} - {new_case.get('title', 'N/A')}")

        # 保存改进后的测试用例到文件
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'agent_results', 'test_case_writer_improved_direct_result.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"test_cases": improved_cases}, f, ensure_ascii=False, indent=2)

        logger.info(f"改进后的测试用例已保存到: {output_path}")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")


if __name__ == '__main__':
    main()