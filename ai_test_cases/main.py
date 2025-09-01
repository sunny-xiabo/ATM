"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: main.py
# @Date: 2025/8/26 16:33
"""

import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import asyncio
from typing import Dict, List, Optional
from src.models.template import Template
from src.utils.agent_io import AgentIO

from src.utils.logger import setup_logger
from src.services.document_prcessor import DocumentProcessor
from src.services.test_case_generator import TestCaseGenerator
from src.services.export_service import ExportService

from src.agents.requirement_analyst import RequirementAnalystAgent
from src.agents.test_designer import TestDesignerAgent
from src.agents.test_case_writer import TestCaseWriterAgent
from src.agents.quality_assurance import QualityAssuranceAgent
from src.agents.assistant import AssistantAgent

# 把项目根目录添加到python路径（不添加，Windows环境可能会报错）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class AITestingSystem:

    def __init__(self, concurrent_workers: int = 1):
        setup_logger()

        # 初始化服务
        self.doc_processor = DocumentProcessor()
        self.test_generator = TestCaseGenerator()
        self.export_service = ExportService()

        # 初始化agents
        self.requirement_analyst = RequirementAnalystAgent()
        self.test_designer = TestDesignerAgent()
        self.test_case_writer = TestCaseWriterAgent(concurrent_workers=concurrent_workers)
        self.quality_assurance = QualityAssuranceAgent(concurrent_workers=concurrent_workers)
        self.assistant = AssistantAgent(
            [self.requirement_analyst, self.test_designer,
             self.test_case_writer, self.quality_assurance]
        )

    async def process_requirements(self,
                                   doc_path: str,
                                   template_path: str,
                                   output_path: Optional[str] = None,
                                   test_type: str = "functional",
                                   input_path: Optional[str] = None) -> Dict:
        """
        处理需求并生成测试用例
        :param doc_path:
        :param template_path:
        :param output_path:
        :param test_type:
        :param input_path:
        :return:
        """
        try:
            # 处理需求文档
            doc_content = await self.doc_processor.process_document(doc_path)
            logger.info(f"已处理需求文档：{doc_path}")

            # 使用assistant协调工作流程，而不是直接调用各个代理
            task = {
                "name": "测试用例生成",
                "description": doc_content
            }
            logger.info("开始协调测试用例生成工作流程")

            try:
                result = await self.assistant.coordinate_workflow(task)
                logger.info(f"工作流程协调结果：{result}")
            except Exception as e:
                logger.error(f"工作流程协调时出错：{str(e)}")
                return {'status': 'error', 'message': f'工作流程协调错误: {str(e)}'}

            # 如果需要修改，返回错误信息
            if result.get("status") == "needs_revison":
                logger.error(f"需求分析结果需要调整：{result.get('message')}")
                return {'status': 'error', 'message': '需求分析结果需要调整'}

            # 从协调结果中获取各个阶段的结果
            requirements = None
            test_strategy = None
            test_cases = None
            reviewed_cases = None

            # 初始化AgentIO用于读取各个agent的结果
            agent_io = AgentIO()
            from src.agents.test_case_writer import TestCaseWriterAgent

            # 首先尝试从agent示例中获取结果
            for agent in self.assistant.agents:
                if isinstance(agent, RequirementAnalystAgent) and hasattr(agent, 'last_analysis'):
                    requirements = agent.last_analysis
                elif isinstance(agent, TestDesignerAgent) and hasattr(agent, 'last_design'):
                    test_strategy = agent.last_design
                elif isinstance(agent, TestCaseWriterAgent) and hasattr(agent, 'last_cases'):
                    test_cases = agent.last_cases
                elif isinstance(agent, QualityAssuranceAgent) and hasattr(agent, 'last_review'):
                    reviewed_cases = agent.last_review

            # 如果从agent实例中没有获取到结果，尝试从持久化存储中读取
            if not requirements:
                requirements = agent_io.load_result("requirement_analyst")
                logger.info("从持久化存储中加载需求分析结果")

            if not test_strategy:
                test_strategy = agent_io.load_result("test_designer")
                logger.info("从持久化存储中加载测试设计结果")

            # 从test_case_writer的持久化存储中加载最终的测试用例
            test_cases_data = agent_io.load_result("test_case_writer")
            logger.info("从test_case_writer的持久化存储中加载最终的测试用例")

            # 确保正确提取test_cases字段
            if isinstance(test_cases_data, dict) and 'test_cases' in test_cases_data:
                test_cases = test_cases_data['test_cases']
            else:
                test_cases = test_cases_data

                # 如果没有获取到任何测试用例，返回错误
            if not test_cases:
                logger.error("没有生成任何测试用例")
                return {'status': 'error', 'message': '没有生成任何测试用例'}

            # 导出测试用例
            if output_path and test_cases:
                # 确保test_cases是列表
                if isinstance(test_cases, dict):
                    test_cases = [test_cases]

                elif not isinstance(test_cases, list):
                    logger.error("测试用例格式错误：必须是字典或字典列表")
                    return {'status': 'error', 'message': '测试用例格式错误'}

                # 确保输出路径包含.xlsx后缀
                if not output_path.endswith('.xlsx'):
                    output_path += '.xlsx'

                # 如果template_path是路径，则从文件加载模板
                if isinstance(template_path, str):
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            template_data = json.load(f)
                        template = Template.from_dict(template_data)
                    except Exception as e:
                        logger.error(f"加载模板时出错：{str(e)}")
                        # 使用默认模板
                        template = Template(
                            "Default Template",
                            "Default test case template"
                        )
                else:
                    # 假设template_path已经是Template对象
                    template = template_path

                await self.export_service.export_to_excel(
                    test_cases,
                    template,
                    output_path
                )
                logger.info(f"测试用例导出成功：{output_path}")

                # 清理测试用例改进过程中生成的临时批次文件
                try:
                    # 查找TestCaseWriterAgent实例并调用清理函数
                    for agent in self.assistant.agents:
                        if isinstance(agent, TestCaseWriterAgent):
                            agent.delete_improved_batch_files()
                            break
                    else:
                        # 如果在agents列表中没有找到，创建一个新实例并调用
                        from src.agents.test_case_writer import TestCaseWriterAgent
                        writer = TestCaseWriterAgent()
                        writer.delete_improved_batch_files()
                        logger.info("已清理测试用例改进过程中生成的临时批次文件")
                except Exception as e:
                    logger.warning(f"清理临时批次文件时出错：{str(e)}")
                    # 继续执行，不影响主流程
            return {
                "status": "success",
                "requirements": requirements,
                "test_strategy": test_strategy,
                "test_cases": test_cases,
                "workflow_result": result
            }


        except Exception as e:
            logger.error(f"处理需求时出错：{e}")
            raise

async def main():
    # 使用命令行参数解析器获取参数
    from src.utils.cli_parser import get_cli_args
    try:
        args = get_cli_args()

        # 创建AITestingSystem实例，传入并发工作线程数
        system = AITestingSystem(concurrent_workers=args.concurrent_workers)
        result = await system.process_requirements(
            doc_path=args.doc_path,
            template_path=args.template_path,
            output_path=args.output_path,
            test_type=args.test_type,
            input_path=args.input_path
        )

        if result.get('status') == 'success':
            print("测试用例生成成功")
            print(f"共生成 {len(result.get('test_cases', []))} 个测试用例")
            print(f"测试类型: {args.test_type}")
            if 'workflow_result' in result:
                print(f"工作流程状态：{result['workflow_result'].get('status','unknown')}")
        else:
            print(f"测试执行失败: {result.get('message', '未知错误')}")
    except Exception as e:
        print(f"程序执行错误: {str(e)}")
        usage = """
        使用方法示例:
        1. 生成测试用例:
            python src/main.py -d docs/需求文档.pdf -t functional -o test_cases.xlsx
        """
        print(usage)

if __name__ == "__main__":
    asyncio.run(main())