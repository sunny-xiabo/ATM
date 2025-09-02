"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: requirement_analyst.py
# @Date: 2025/8/27 14:30
"""

import logging
import os
import re
import time
from typing import Dict, List

import autogen
from dotenv import load_dotenv
from src.utils.agent_io import AgentIO
from src.schemas.communication import TestScenario
from src.utils.json_parser import UnifiedJSONParser

load_dotenv()  # 加载环境变量
logger = logging.getLogger(__name__)  # 获取日志记录器

api_key = os.getenv("LLM_KEY")
base_url = os.getenv("BASE_URL")
model = os.getenv("LLM_MODEL")


class RequirementAnalystAgent:

    def __init__(self):
        self.config_list = [
            {
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
            }
        ]

        # 初始化AgentIO用于保存和加载分析结果
        self.agent_io = AgentIO()

        # 初始化统一的JSON解析器
        self.json_parser = UnifiedJSONParser()

        self.agent = autogen.AssistantAgent(
            name="requirement_analyst",
            system_message=
            '''
                你是一位专业的需求分析师，专注于软件测试领域。你的职责是分析软件需求，识别关键测试领域、功能流程和潜在风险。
                请按照以下 JSON 格式提供分析结果：
                {
                    "functional_requirements": [
                        "功能需求1",
                        "功能需求2"
                    ],
                    "non_functional_requirements": [
                        "非功能需求1",
                        "非功能需求2"
                    ],
                    "test_scenarios": [
                        {
                            "id": "TS001", # 测试用例编号
                            "description": "", # 测试用例描述
                            "test_cases": [] #具体测试用例
                        },
                        {
                            "id": "TS002",
                            "description": "",
                            "test_cases": []
                        },
                        {
                            "id": "TS003",
                            "description": "",
                            "test_cases": []
                        },
                        {
                            "id": "TS004",
                            "description": "",
                            "test_cases": []
                        }
                    ],
                    "risk_areas": [
                        "风险领域1",
                        "风险领域2"
                    ]
                }
    
                注意：
                1. 所有输出必须严格遵循上述 JSON 格式
                2. 每个数组至少包含一个有效项
                3. 所有文本必须使用双引号
                4. JSON 必须是有效的且可解析的
                5. 每个测试场景必须包含所有必需字段（id、description、test_cases）
                6. 返回的内容必须是中文回复，不要英文回复
                7. id等键名必须按照json里的格式返回，如"id": "TC001-修改密码为空"这种
                8. 请仔细阅读需求文档，提取出所有功能需求、非功能需求、测试场景、风险领域，不要遗漏，并明确每个需求和功能下的具体规则
                9. 并把分析出的功能规则，分配到每一条测试用例中，并把对应的规则添加到description测试用例描述中
                10. 每个需求和功能下（）括号内的内容也应该仔细分析，并添加到description测试用例描述中
                11. 分析完需求后也要再核对以下需求文档，看是否有遗漏的功能点，如有，需补充完整
            ''',
            llm_config={"config_list": self.config_list},
        )

        # 添加last_analysis属性，用于跟踪最近的分析结果
        self.last_analysis = None

    def analyze(self, doc_content: str) -> Dict:
        """分析需求文档并提取测试需求。"""
        try:
            start_time = time.time()
            # 检查输入文档是否为空
            if not doc_content or not doc_content.strip():
                logger.warning("输入文档为空，返回默认分析结果")
                from src.schemas.communication import TestScenario
                default_result = {
                    "functional_requirements": ["需要提供具体的功能需求"],
                    "non_functional_requirements": ["需要提供具体的非功能需求"],
                    "test_scenarios": [
                        TestScenario(
                            id="TS001",
                            description="需要提供具体的测试场景",
                            test_cases=[]
                        )
                    ],
                    "risk_areas": ["需要评估具体的风险领域"]
                }
                self.last_analysis = default_result
                return default_result

            # 创建用户代理进行交互
            user_proxy = autogen.UserProxyAgent(
                name="user_proxy",
                system_message="需求文档提供者",
                human_input_mode="NEVER",
                code_execution_config={"use_docker": False}
            )

            # 构建消息内容
            message_content = "请分析以下需求文档并提取关键测试点，必须以JSON格式返回结果：\n\n"
            message_content += doc_content
            message_content += "\n\n你必须严格按照以下JSON格式提供分析结果：\n"
            message_content += """
    {
        "functional_requirements": [], #功能需求
        "non_functional_requirements": [], #非功能需求
        "test_scenarios": [], #测试场景
        "risk_areas": [] #风险点
    }
                """
            message_content += "\n\n注意：\n"
            message_content += "1. 必须返回有效的JSON格式\n"
            message_content += "2. 所有文本必须使用双引号\n"
            message_content += "3. 每个数组至少包含一个项目\n"
            message_content += "4. 不要添加任何额外的说明文字\n"

            # 初始化需求分析对话
            user_proxy.initiate_chat(
                self.agent,
                message=message_content,
                max_turns=1
            )

            # 处理代理响应并生成标准JSON
            try:
                response = self.agent.last_message()
                if not response:
                    logger.warning("需求分析代理返回空响应")
                    return self._get_default_result()

                # 确保response是字符串类型
                if isinstance(response, dict) and 'content' in response:
                    response_str = response['content']
                else:
                    response_str = str(response)

                logger.info(f"AI响应内容: {response_str[:200]}...")  # 只打印前200个字符避免日志过长

                # 导入TestScenario类
                from src.schemas.communication import TestScenario

                # 使用统一的JSON解析器
                structured_result = self.json_parser.parse(response_str, "requirement_analysis")

                if structured_result:
                    # 构建结构化结果
                    structured_result = self._build_structured_result(structured_result)
                    logger.info("成功从JSON响应中提取分析结果")
                else:
                    logger.warning("无法从响应中提取有效的JSON，尝试使用文本解析方法")
                    # 使用文本解析方法作为备用方案
                    structured_result = {
                        "functional_requirements": self._extract_functional_reqs(response_str),
                        "non_functional_requirements": self._extract_non_functional_reqs(response_str),
                        "test_scenarios": self._extract_test_scenarios(response_str),
                        "risk_areas": self._extract_risk_areas(response_str)
                    }

                    # 验证结果并填充缺失字段
                if not self._validate_analysis_result(structured_result):
                    logger.warning("分析结果验证失败，填充缺失字段")
                    self._fill_missing_requirements(structured_result)

                    # 保存分析结果
                self.agent_io.save_result('requirement_analyst', structured_result)

                # 保存到last_analysis属性
                self.last_analysis = structured_result

                # 返回结构化的字典对象
                return structured_result

            except Exception as e:
                logger.error(f"JSON生成失败: {str(e)}")
                return {
                    "error": "结果生成失败",
                    "details": str(e)
                }
        except Exception as e:
            logger.error(f"需求分析错误: {str(e)}")
            raise

    def _extract_functional_reqs(self, message: str) -> List[str]:
        """从代理消息中提取功能需求。"""
        try:
            if not message:
                logger.warning("输入消息为空")
                return []

            # 将消息分割成段落并找到功能需求部分
            sections = message.split('\n')
            functional_reqs = []
            in_functional_section = False

            for line in sections:
                # 清理特殊字符和空白
                line = ''.join(char for char in line.strip() if ord(char) >= 32)
                if not line:
                    continue

                # 支持多种标题格式（增强匹配逻辑）
                cleaned_line = line.lower().replace('：', ':').replace(' ', '')
                # 扩展标题关键词匹配范围
                title_patterns = [
                    '功能需求', 'functionalrequirements', '功能列表', '功能点',
                    'feature', 'functional spec', '功能规格', '核心功能'
                ]
                exit_patterns = [
                    '非功能需求', 'non-functional', '非功能性需求',
                    '性能需求', '约束条件', '测试场景'
                ]

                if any(marker in cleaned_line for marker in title_patterns):
                    in_functional_section = True
                    logger.debug(f"进入功能需求解析区块: {line}")
                    continue
                elif any(marker in cleaned_line for marker in exit_patterns):
                    in_functional_section = False
                    logger.debug(f"退出功能需求解析区块: {line}")
                    break
                elif in_functional_section:
                    # 改进内容提取逻辑（支持更多格式）
                    content = line.strip()

                    # 处理带编号的条目（增强正则表达式，支持中文数字）
                    numbered_pattern = r'^[(（\[【]?[\dA-Za-z一二三四五六七八九十][\]）】\.、]'
                    if re.match(numbered_pattern, content):
                        content = re.sub(numbered_pattern, '', content).strip()
                        logger.debug(f"处理编号内容: {content}")

                    # 处理项目符号（扩展符号列表，增加中英文符号）
                    bullet_pattern = r'^[\-\*•›➢▷✓✔⦿◉◆◇■□●○]'
                    if re.match(bullet_pattern, content):
                        content = content[1:].strip()
                        logger.debug(f"处理项目符号内容: {content}")

                    # 清理特殊字符（增加现代符号过滤）
                    content = re.sub(r'[【】〖〗“”‘’😀-🙏§※★☆♀♂]', '', content).strip()

                    # 智能过滤条件（增加业务动词校验）
                    business_verbs = ['应', '需要', '支持', '实现', '提供', '确保', '允许']
                    if content and 3 < len(content) < 100 and any(verb in content for verb in business_verbs):
                        logger.info(f"有效功能需求: {content}")
                        functional_reqs.append(content)
                        continue

                    # 记录过滤详情便于调试
                    logger.warning(
                        f"过滤无效内容 | 原句: {line} | 处理后: {content} | 原因: {'长度不符' if len(content) <= 3 or len(content) >= 100 else '缺少业务动词'}")
                    content = re.sub(r'[【】〖〗“”‘’😀-🙏]', '', content).strip()
                    content = re.sub(r'[【】〖〗“”‘’]', '', content).strip()

                    # 智能过滤条件（保留包含动词的条目）
                    if content and len(content) > 3 and not re.search(r'[：:]$', content):
                        # 记录解析过程
                        logger.debug(f"提取到功能需求条目: {content}")
                        functional_reqs.append(content)
                        continue

                    logger.debug(f"过滤无效内容: {line}")
                    # 如果内容以破折号开头，去掉破折号
                    if content.startswith('-'):
                        content = content[1:].strip()
                    functional_reqs.append(content)

            # 如果没有找到任何功能需求，返回默认值
            if not functional_reqs:
                logger.warning("未找到有效的功能需求，使用默认值")
                functional_reqs = ["需要提供具体的功能需求"]
            else:
                logger.info(f"成功提取{len(functional_reqs)}个功能需求")

            return functional_reqs
        except Exception as e:
            logger.error(f"提取功能需求错误: {str(e)}")
            return []

    def _extract_non_functional_reqs(self, message: str) -> List[str]:
        """从代理消息中提取非功能需求。"""
        try:
            if not message:
                logger.warning("输入消息为空")
                return []

            sections = message.split('\n')
            non_functional_reqs = []
            in_non_functional_section = False

            for line in sections:
                line = ''.join(char for char in line.strip() if ord(char) >= 32)
                if not line:
                    continue

                # 支持多种标题格式
                if any(marker in line.lower() for marker in
                       ['2. 非功能需求', '非功能需求:', '非功能需求：', '### 2. 非功能需求']):
                    in_non_functional_section = True
                    continue
                elif any(marker in line.lower() for marker in
                         ['3. 测试场景', '测试场景:', '测试场景：', '### 3. 测试场景']):
                    in_non_functional_section = False
                    break
                elif in_non_functional_section:
                    # 过滤掉编号和空行
                    content = line
                    # 处理带有编号、破折号或其他标记的行
                    if content.startswith(('-', '*', '•')):
                        content = content[1:].strip()
                    elif any(char.isdigit() for char in line[:2]):
                        for sep in ['.', '、', '）', ')', ']']:
                            if sep in line:
                                try:
                                    content = line.split(sep, 1)[1]
                                    break
                                except IndexError:
                                    continue
                    content = content.strip()
                    # 过滤掉标题行、空内容和特殊标记
                    if content and not any(content.lower().startswith(prefix.lower()) for prefix in
                                           ['2.', '二、', '非功能需求', '需求', '要求', '**', '#']):
                        # 如果内容以破折号开头，去掉破折号
                        if content.startswith('-'):
                            content = content[1:].strip()
                        non_functional_reqs.append(content)

            return non_functional_reqs
        except Exception as e:
            logger.error(f"提取非功能需求错误: {str(e)}")
            return []

    def _extract_test_scenarios(self, message: str) -> List[TestScenario]:
        """从代理消息中提取测试场景，并转换为TestScenario对象列表。"""
        try:
            if not message:
                logger.warning("输入消息为空")
                return []

            sections = message.split('\n')
            scenario_descriptions = []
            in_scenarios_section = False

            for line in sections:
                line = ''.join(char for char in line.strip() if ord(char) >= 32)
                if not line:
                    continue

                # 支持多种标题格式
                if any(marker in line.lower() for marker in
                       ['3. 测试场景', '测试场景:', '测试场景：', '### 3. 测试场景']):
                    in_scenarios_section = True
                    continue
                elif any(marker in line.lower() for marker in
                         ['4. 风险领域', '风险领域:', '风险领域：', '### 4. 风险领域']):
                    in_scenarios_section = False
                    break
                elif in_scenarios_section:
                    # 过滤掉编号和空行
                    content = line
                    # 处理带有编号、破折号或其他标记的行
                    if content.startswith(('-', '*', '•')):
                        content = content[1:].strip()
                    elif any(char.isdigit() for char in line[:2]):
                        for sep in ['.', '、', '）', ')', ']']:
                            if sep in line:
                                try:
                                    content = line.split(sep, 1)[1]
                                    break
                                except IndexError:
                                    continue
                    content = content.strip()
                    # 过滤掉标题行、空内容和特殊标记
                    if content and not any(content.lower().startswith(prefix.lower()) for prefix in
                                           ['3.', '三、', '测试场景', '场景', '**', '#']):
                        # 如果内容以破折号开头，去掉破折号
                        if content.startswith('-'):
                            content = content[1:].strip()
                        scenario_descriptions.append(content)

            # 将提取的描述转换为TestScenario对象
            test_scenarios = []
            for i, description in enumerate(scenario_descriptions):
                scenario_id = f"TS{(i + 1):03d}"  # 生成格式为TS001, TS002的ID
                test_scenarios.append(TestScenario(
                    id=scenario_id,
                    description=description,
                    test_cases=[]
                ))

            # 如果没有提取到任何场景，添加一个默认场景
            if not test_scenarios:
                test_scenarios.append(TestScenario(
                    id="TS001",
                    description="需要提供具体的测试场景",
                    test_cases=[]
                ))

            return test_scenarios
        except Exception as e:
            logger.error(f"提取测试场景错误: {str(e)}")
            # 返回一个默认的TestScenario对象
            return [TestScenario(
                id="TS001",
                description="提取测试场景时发生错误",
                test_cases=[]
            )]

    def _extract_risk_areas(self, message: str) -> List[str]:
        """从代理消息中提取风险领域。"""
        try:
            if not message:
                logger.warning("输入消息为空")
                return []

            sections = message.split('\n')
            risk_areas = []
            in_risks_section = False

            for line in sections:
                line = ''.join(char for char in line.strip() if ord(char) >= 32)
                if not line:
                    continue

                # 支持多种标题格式
                if any(marker in line.lower() for marker in
                       ['4. 风险领域', '风险领域:', '风险领域：', '### 4. 风险领域']):
                    in_risks_section = True
                    continue
                elif line.startswith('5.') or not line.strip():
                    in_risks_section = False
                    break
                elif in_risks_section:
                    # 过滤掉编号和空行
                    content = line
                    # 处理带有编号、破折号或其他标记的行
                    if content.startswith(('-', '*', '•')):
                        content = content[1:].strip()
                    elif any(char.isdigit() for char in line[:2]):
                        for sep in ['.', '、', '）', ')', ']']:
                            if sep in line:
                                try:
                                    content = line.split(sep, 1)[1]
                                    break
                                except IndexError:
                                    continue
                    content = content.strip()
                    # 过滤掉标题行、空内容和特殊标记
                    if content and not any(content.lower().startswith(prefix.lower()) for prefix in
                                           ['4.', '四、', '风险领域', '风险', '**', '#']):
                        # 如果内容以破折号开头，去掉破折号
                        if content.startswith('-'):
                            content = content[1:].strip()
                        risk_areas.append(content)

            return risk_areas
        except Exception as e:
            logger.error(f"提取风险领域错误: {str(e)}")
            return []

    def _validate_analysis_result(self, result: Dict) -> bool:
        """验证分析结果的完整性。"""
        required_keys = ['functional_requirements', 'non_functional_requirements',
                         'test_scenarios', 'risk_areas']

        # 检查所有必需的键是否存在且不为空
        for key in required_keys:
            if key not in result or not isinstance(result[key], list):
                return False
        return True

    def _fill_missing_requirements(self, result: Dict):
        """填充缺失的需求字段。"""
        default_value = ["需要补充具体内容"]
        required_keys = ['functional_requirements', 'non_functional_requirements',
                         'test_scenarios', 'risk_areas']

        for key in required_keys:
            if key not in result or not result[key]:
                result[key] = default_value.copy()

    def _get_default_result(self):
        """返回默认的分析结果。"""
        from src.schemas.communication import TestScenario
        default_result = {
            "functional_requirements": ["需要提供具体的功能需求"],
            "non_functional_requirements": ["需要提供具体的非功能需求"],
            "test_scenarios": [
                TestScenario(
                    id="TS001",
                    description="需要提供具体的测试场景",
                    test_cases=[]
                )
            ],
            "risk_areas": ["需要评估具体的风险领域"]
        }
        self.last_analysis = default_result
        return default_result

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _build_structured_result(self, parsed_result: Dict) -> Dict:
        """构建结构化的分析结果"""
        structured_result = {
            "functional_requirements": parsed_result.get("functional_requirements", []),
            "non_functional_requirements": parsed_result.get("non_functional_requirements", []),
            "risk_areas": parsed_result.get("risk_areas", [])
        }

        # 处理test_scenarios字段
        if "test_scenarios" in parsed_result and isinstance(parsed_result["test_scenarios"], list):
            test_scenarios = []
            for scenario in parsed_result["test_scenarios"]:
                if isinstance(scenario, dict):
                    test_scenarios.append(TestScenario(
                        id=scenario.get("id", f"TS{len(test_scenarios) + 1:03d}"),
                        description=scenario.get("description", ""),
                        test_cases=scenario.get("test_cases", [])
                    ))
            structured_result["test_scenarios"] = test_scenarios
        else:
            structured_result["test_scenarios"] = [
                TestScenario(
                    id="TS001",
                    description="需要提供具体的测试场景",
                    test_cases=[]
                )
            ]

        return structured_result
