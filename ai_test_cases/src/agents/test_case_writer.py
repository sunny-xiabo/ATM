"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: test_case_writer_test.py
# @Date: 2025/8/28 09:35
"""

import logging
import os
import re
import json
from typing import Dict, List, Union

import autogen
from dotenv import load_dotenv
from src.utils.agent_io import AgentIO
from src.utils.json_parser import UnifiedJSONParser

load_dotenv()  # 加载环境变量
logger = logging.getLogger(__name__)  # 获取日志记录器

api_key = os.getenv("LLM_KEY")
base_url = os.getenv("BASE_URL")
model = os.getenv("LLM_MODEL")


class TestCaseWriterAgent:
    def __init__(self, concurrent_workers: int = 1):
        self.config_list = [
            {
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
            }
        ]

        # 初始化AgentIO用于保存和加载测试用例
        self.agent_io = AgentIO()

        # 初始化统一的JSON解析器
        self.json_parser = UnifiedJSONParser()

        # 设置并发工作线程数
        self.concurrent_workers = max(1, concurrent_workers)  # 确保至少有一个线程
        logger.info(f"测试用例编写代理初始化，设置并发工作线程数为: {self.concurrent_workers}")

        self.agent = autogen.AssistantAgent(
            name="test_case_writer",
            system_message='''
            你是一位精确的测试用例编写者。你的职责是基于测试
            策略创建详细、清晰且可执行的测试用例。

            请按照以下 JSON 格式提供测试用例：
            {
                "test_cases": [
                    {
                        "id": "TC001",
                        "title": "测试用例标题",
                        "preconditions": [
                            "前置条件1",
                            "前置条件2"
                        ],
                        "steps": [
                            "测试步骤1",
                            "测试步骤2"
                        ],
                        "expected_results": [
                            "预期结果1",
                            "预期结果2"
                        ],
                        "priority": "P0",
                        "category": "功能测试" # 也可以是其他测试类型或几个类型
                    }
                ]
            }

            1. 所有输出必须严格遵循上述 JSON 格式
            2. 每个数组至少包含一个有效项
            3. 所有文本必须使用双引号
            4. JSON 必须是有效的且可解析的
            5. 每个测试用例必须包含所有必需字段，包括description描述
            6. description字段应该详细描述测试用例的目的、范围和测试重点
            7. 返回的内容必须是中文回复，不要英文回复
            8. id等键名必须按照json里的格式返回，如"id": "TC001-修改密码为空"这种
            ''',
            llm_config={"config_list": self.config_list},
        )

        # 添加last_cases属性，用于跟踪最近生成的测试用例
        self.last_cases = None

        # 尝试加载之前的测试用例结果
        self._load_last_cases()

    def _load_last_cases(self):
        """加载之前保存的测试用例结果"""
        try:
            result = self.agent_io.load_result("test_case_writer")
            if result:
                self.last_cases = result
                logger.info("成功加载之前的测试用例生成结果")
        except Exception as e:
            logger.error(f"加载测试用例结果时出错: {str(e)}")

    def generate(self, test_strategy: Dict) -> List[Dict]:
        """基于测试策略生成测试用例。
        优化：按功能点分批生成测试用例，避免一次处理过多导致超时或输出不完整。
        """
        try:
            # 提取测试覆盖矩阵和优先级信息
            coverage_matrix = test_strategy.get('coverage_matrix', [])
            priorities = test_strategy.get('priorities', [])
            test_approach = test_strategy.get('test_approach', {})

            # 如果没有覆盖矩阵，使用原来的方法生成测试用例
            if not coverage_matrix:
                logger.warning("未提供测试覆盖矩阵，将使用整体生成方式")
                return self._generate_all_test_cases(test_strategy)

            # 按功能点分组
            feature_groups = {}
            for item in coverage_matrix:
                feature = item.get('feature', '')
                if not feature:
                    continue

                if feature not in feature_groups:
                    feature_groups[feature] = []
                feature_groups[feature].append(item)

            logger.info(f"将按{len(feature_groups)}个功能点分批生成测试用例")

            # 根据并发工作线程数决定使用并发还是顺序处理
            if self.concurrent_workers > 1:
                logger.info(f"使用并发方式处理功能点，并发数: {self.concurrent_workers}")
                all_test_cases = self._generate_feature_test_cases_concurrent(
                    feature_groups=feature_groups,
                    priorities=priorities,
                    test_approach=test_approach
                )
            else:
                logger.info("使用顺序方式处理功能点")
                # 分批生成测试用例
                all_test_cases = []
                for i, (feature, items) in enumerate(feature_groups.items()):
                    logger.info(f"开始为功能点 '{feature}' 生成测试用例 ({i + 1}/{len(feature_groups)})")

                    # 为单个功能点生成测试用例
                    feature_test_cases = self._generate_feature_test_cases(
                        feature=feature,
                        feature_items=items,
                        priorities=priorities,
                        test_approach=test_approach
                    )

                    if feature_test_cases:
                        all_test_cases.extend(feature_test_cases)
                        logger.info(f"功能点 '{feature}' 生成了 {len(feature_test_cases)} 个测试用例")

                        # 保存中间结果，防止因超时丢失数据
                        temp_result = {
                            "test_cases": feature_test_cases,  # 只保存当前功能点的测试用例
                            "generation_date": self._get_current_timestamp(),
                            "generation_status": "in_progress",
                            "feature_progress": f"{i + 1}/{len(feature_groups)}"
                        }
                        try:
                            self.agent_io.save_result(f"test_case_writer_feature_{i + 1}", temp_result)
                            logger.info(f"已保存功能点 '{feature}' 的测试用例生成结果")
                        except Exception as e:
                            logger.error(f"保存功能点 '{feature}' 的测试用例生成结果时出错: {str(e)}")
                    else:
                        logger.warning(f"功能点 '{feature}' 未能生成有效的测试用例")

            # 如果没有生成任何测试用例，尝试使用整体生成方式
            if not all_test_cases:
                logger.warning("按功能点分批生成未产生有效测试用例，尝试使用整体生成方式")
                return self._generate_all_test_cases(test_strategy)

            # 验证测试用例是否与测试覆盖矩阵对应
            self._validate_coverage(all_test_cases, coverage_matrix)

            # 保存测试用例到last_cases属性
            self.last_cases = all_test_cases
            logger.info(f"测试用例生成完成，共生成 {len(all_test_cases)} 个测试用例")

            # 将测试用例保存到文件
            self.agent_io.save_result("test_case_writer", {"test_cases": all_test_cases})

            # 合并所有功能点的测试用例文件
            self._merge_feature_test_cases(len(feature_groups))

            return all_test_cases

        except Exception as e:
            logger.error(f"测试用例生成错误: {str(e)}")
            raise

    def _generate_all_test_cases(self, test_strategy: Dict) -> List[Dict]:
        """使用整体方式生成所有测试用例。"""
        try:
            user_proxy = autogen.UserProxyAgent(
                name="user_proxy",
                system_message="测试策略提供者",
                human_input_mode="NEVER",
                code_execution_config={"use_docker": False}
            )

            # 提取测试覆盖矩阵和优先级信息
            coverage_matrix = test_strategy.get('coverage_matrix', [])
            priorities = test_strategy.get('priorities', [])
            test_approach = test_strategy.get('test_approach', {})

            # 构建更详细的提示，包含覆盖矩阵和优先级信息
            coverage_info = "\n测试覆盖矩阵:\n"
            for item in coverage_matrix:
                coverage_info += f"- 功能: {item.get('feature', '')}, 测试类型: {item.get('test_type', '')}\n"

            priority_info = "\n测试优先级:\n"
            for item in priorities:
                priority_info += f"- {item.get('level', '')}: {item.get('description', '')}\n"

            approach_info = "\n测试方法:\n"
            if isinstance(test_approach, dict):
                for key, value in test_approach.items():
                    if isinstance(value, list):
                        approach_info += f"- {key}: {', '.join(value)}\n"
                    else:
                        approach_info += f"- {key}: {value}\n"

            # 生成测试用例
            user_proxy.initiate_chat(
                self.agent,
                message=f"""基于以下测试策略创建详细的测试用例：

                {approach_info}
                {coverage_info}
                {priority_info}

                请确保每个测试用例都对应测试覆盖矩阵中的一个或多个功能点，并遵循定义的优先级策略。
                测试用例的优先级必须使用测试优先级中定义的级别（如P0、P1等）。
                测试用例的类别应该与测试覆盖矩阵中的测试类型相对应。

                重要：
                + 必须为测试覆盖矩阵中的每个功能点至少创建一个测试用例，确保100%覆盖所有功能点。
                + 不只覆盖功能测试，非功能测试、风险点等，也要确保100%覆盖。

                对每个测试用例，请提供：
                1. 用例ID
                2. 标题
                3. 描述（详细说明测试的目的和范围）
                4. 前置条件
                5. 测试步骤
                6. 预期结果
                7. 优先级（使用上述优先级定义）
                8. 类别（对应测试覆盖矩阵中的测试类型）

                请直接提供测试用例，无需等待进一步确认。""",
                max_turns=1  # 限制对话轮次为1，避免死循环
            )

            # 尝试解析测试用例
            last_message = self.agent.last_message()
            if not last_message:
                logger.warning("未能获取到agent的最后一条消息")
                return []

            test_cases = self._parse_test_cases(last_message)

            # 如果解析结果为空，尝试重新生成一次
            if not test_cases:
                logger.warning("第一次测试用例生成为空，尝试重新生成")

                # 构建更明确的提示，强调必须基于测试覆盖矩阵和优先级
                retry_message = f"""请重新创建测试用例，确保严格按照测试设计生成。

                测试覆盖矩阵中的每个测试点都必须有对应的测试用例：
                {coverage_info}

                测试用例必须使用以下优先级：
                {priority_info}

                每个测试用例必须包含：ID、标题、描述、前置条件、测试步骤、预期结果、优先级和类别。
                优先级必须使用P0、P1等格式，类别必须与测试覆盖矩阵中的测试类型对应。

                重要：
                + 必须为测试覆盖矩阵中的每个功能点至少创建一个测试用例，确保100%覆盖所有功能点。
                + 不只覆盖功能测试，非功能测试、风险点等，也要确保100%覆盖。

                请以JSON格式返回测试用例，确保格式正确。"""

                # 重新尝试生成测试用例
                user_proxy.initiate_chat(
                    self.agent,
                    message=retry_message,
                    max_turns=1
                )

                # 再次解析测试用例
                last_message = self.agent.last_message()
                if not last_message:
                    logger.warning("重试时未能获取到agent的最后一条消息")
                    return []

                test_cases = self._parse_test_cases(last_message)

                # 如果仍然为空，记录错误并返回空列表
                if not test_cases:
                    logger.error("重新生成测试用例仍然失败，无法生成符合测试设计的测试用例")
                    return []

            # 验证测试用例是否与测试覆盖矩阵对应
            if coverage_matrix and test_cases:
                # 提取功能点和测试类型的映射关系
                feature_type_map = {}
                for item in coverage_matrix:
                    feature = item.get('feature', '')
                    test_type = item.get('test_type', '')
                    if feature not in feature_type_map:
                        feature_type_map[feature] = set()
                    if isinstance(test_type, str):
                        for t in test_type.split(','):
                            feature_type_map[feature].add(t.strip())
                    else:
                        feature_type_map[feature].add(test_type)

                # 检查每个功能点是否被测试用例覆盖
                covered_features = set()
                for tc in test_cases:
                    # 从测试用例标题中提取可能的功能点
                    title = tc.get('title', '').lower()
                    for feature in feature_type_map.keys():
                        if feature.lower() in title:
                            covered_features.add(feature)

                # 记录覆盖情况
                logger.info(f"测试覆盖矩阵测试点总数: {len(feature_type_map)}")
                logger.info(f"已覆盖测试点数量: {len(covered_features)}")

                # 检查是否有未覆盖的功能点
                uncovered = set(feature_type_map.keys()) - covered_features
                if uncovered:
                    logger.warning(f"以下测试点未被测试用例覆盖: {uncovered}")

                    # 如果覆盖率低于80%，记录警告
                    coverage_rate = len(covered_features) / len(feature_type_map) if feature_type_map else 1.0
                    if coverage_rate < 0.8:
                        logger.warning(f"测试用例覆盖率过低: {coverage_rate:.2%}，建议增加测试用例数量")

            return test_cases

        except Exception as e:
            logger.error(f"测试用例生成错误: {str(e)}")
            raise

    def _parse_test_cases(self, message) -> List[Dict]:
        """解析Agent响应为结构化的测试用例。"""
        try:
            # 检查message类型
            if isinstance(message, dict):
                # 如果是字典，尝试从content字段获取内容
                if 'content' in message:
                    message = message['content']
                else:
                    logger.error(f"无法从字典中提取消息内容: {message}")
                    return []

            # 确保message是字符串
            if not isinstance(message, str):
                logger.error(f"消息不是字符串类型: {type(message)}")
                return []

            # 使用统一的JSON解析器
            json_data = self.json_parser.parse(message, "test_case_generation")

            if json_data and 'test_cases' in json_data and isinstance(json_data['test_cases'], list):
                logger.info(f"成功从JSON响应中解析出 {len(json_data['test_cases'])} 个测试用例")

                # 验证和规范化测试用例
                validated_test_cases = []
                for test_case in json_data['test_cases']:
                    # 确保所有必需字段都存在
                    if self._validate_test_case(test_case):
                        # 规范化优先级格式（确保是P0、P1等格式）
                        if 'priority' in test_case and not test_case['priority'].startswith('P'):
                            test_case['priority'] = f"P{test_case['priority']}" if test_case['priority'].isdigit() else \
                                test_case['priority']

                        # 确保类别字段存在且有意义
                        if 'category' not in test_case or not test_case['category']:
                            test_case['category'] = '功能测试'

                        validated_test_cases.append(test_case)
                    else:
                        logger.warning(f"测试用例验证失败，跳过: {test_case.get('id', 'unknown')}")

                # 如果验证后的测试用例为空，记录警告并返回空列表
                if not validated_test_cases:
                    logger.warning("验证后的测试用例为空，需要重新生成")
                    return []

                return validated_test_cases

            # 如果没有找到JSON格式的响应，尝试使用原来的解析方法
            sections = message.split('\n')
            test_cases = []
            current_test_case = None
            current_field = None

            for line in sections:
                line = line.strip()
                if not line:
                    continue

                # 当找到ID时开始新的测试用例
                if line.lower().startswith('id:'):
                    if current_test_case:
                        if self._validate_test_case(current_test_case):
                            # 规范化优先级格式
                            if 'priority' in current_test_case and not current_test_case['priority'].startswith('P'):
                                current_test_case['priority'] = f"P{current_test_case['priority']}" if \
                                    current_test_case['priority'].isdigit() else current_test_case['priority']
                            test_cases.append(current_test_case)
                    current_test_case = {
                        'id': '',
                        'title': '',
                        'description': '',
                        'preconditions': [],
                        'steps': [],
                        'expected_results': [],
                        'priority': '',
                        'category': ''
                    }
                    current_test_case['id'] = line.split(':', 1)[1].strip()
                    current_field = 'id'

                # 识别当前正在处理的字段
                elif line.lower().startswith('title:'):
                    # 如果遇到标题字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    # 增加空值检查,避免split返回None
                    title_parts = line.split(':', 1) if line else ['', '']
                    current_test_case['title'] = title_parts[1].strip() if len(title_parts) > 1 else ''
                    current_field = 'title'
                elif line.lower().startswith('description:'):
                    # 如果遇到描述字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_test_case['description'] = line.split(':', 1)[1].strip() if len(
                        line.split(':', 1)) > 1 else ''
                    current_field = 'description'
                elif line.lower().startswith('preconditions:'):
                    # 如果遇到前置条件字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_field = 'preconditions'
                elif line.lower().startswith('steps:'):
                    # 如果遇到步骤字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_field = 'steps'
                elif line.lower().startswith('expected results:'):
                    # 如果遇到预期结果字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_field = 'expected_results'
                elif line.lower().startswith('priority:'):
                    # 如果遇到优先级字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_test_case['priority'] = line.split(':', 1)[1].strip()
                    current_field = 'priority'
                elif line.lower().startswith('category:'):
                    # 如果遇到类别字段但当前测试用例为空，先创建一个新的测试用例
                    if not current_test_case:
                        current_test_case = {
                            'id': f'TC{len(test_cases) + 1:03d}',  # 自动生成ID
                            'title': '',
                            'description': '',
                            'preconditions': [],
                            'steps': [],
                            'expected_results': [],
                            'priority': '',
                            'category': ''
                        }
                    current_test_case['category'] = line.split(':', 1)[1].strip()
                    current_field = 'category'

                # 添加内容到当前字段
                elif current_test_case and current_field:
                    if current_field in ['preconditions', 'steps', 'expected_results']:
                        if line.strip().startswith('-'):
                            current_test_case[current_field].append(line.strip()[1:].strip())
                        elif line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '0.')):
                            current_test_case[current_field].append(line.strip().split('.', 1)[1].strip())
                    elif current_field in ['description', 'title']:
                        # 对于字符串字段，如果当前行不是新的字段标识，则追加到现有内容
                        if not any(line.lower().startswith(field + ':') for field in
                                   ['id:', 'title:', 'description:', 'preconditions:', 'steps:', 'expected results:',
                                    'priority:', 'category:']):
                            if current_test_case[current_field]:  # 如果已有内容，添加换行
                                current_test_case[current_field] += ' ' + line.strip()
                            else:  # 如果没有内容，直接设置
                                current_test_case[current_field] = line.strip()

            # 如果存在最后一个测试用例则添加
            if current_test_case and self._validate_test_case(current_test_case):
                # 规范化优先级格式
                if 'priority' in current_test_case and not current_test_case['priority'].startswith('P'):
                    current_test_case['priority'] = f"P{current_test_case['priority']}" if current_test_case[
                        'priority'].isdigit() else current_test_case['priority']
                test_cases.append(current_test_case)

            # 如果没有解析出任何测试用例，返回空列表
            if not test_cases:
                logger.warning("未能解析出任何测试用例，需要重新生成")
                return []

            return test_cases
        except Exception as e:
            logger.error(f"解析测试用例错误: {str(e)}")
            return []

    def _validate_test_case(self, test_case: Dict) -> bool:
        """验证测试用例的结构和内容。"""
        try:
            # 检查是否所有必需字段都存在
            required_fields = [
                "id", "title", "description", "preconditions", "steps",
                "expected_results", "priority", "category"
            ]
            if not all(field in test_case for field in required_fields):
                logger.warning(
                    f"测试用例缺少必需字段: {[field for field in required_fields if field not in test_case]}")
                return False

            # 验证字段内容
            if not test_case["id"] or not test_case["title"]:
                logger.warning(f"测试用例ID或标题为空: {test_case.get('id', 'unknown')}")
                return False

            # 验证描述字段
            if not test_case["description"]:
                logger.warning(f"测试用例描述为空: {test_case.get('id', 'unknown')}")
                return False

            # 确保步骤和预期结果不为空
            if not test_case["steps"] or not test_case["expected_results"]:
                logger.warning(f"测试用例步骤或预期结果为空: {test_case.get('id', 'unknown')}")
                return False

            # 验证优先级格式（如 P0, P1, P2）
            # 注意：我们在解析时会规范化优先级格式，所以这里不再严格要求格式
            if not test_case["priority"]:
                logger.warning(f"测试用例优先级为空: {test_case.get('id', 'unknown')}")
                return False

            # 验证类别不为空
            if not test_case["category"]:
                logger.warning(f"测试用例类别为空: {test_case.get('id', 'unknown')}")
                return False

            # 验证前置条件是否为列表
            if not isinstance(test_case["preconditions"], list):
                logger.warning(f"测试用例前置条件不是列表: {test_case.get('id', 'unknown')}")
                test_case["preconditions"] = [test_case["preconditions"]] if test_case["preconditions"] else []

            # 验证步骤是否为列表
            if not isinstance(test_case["steps"], list):
                logger.warning(f"测试用例步骤不是列表: {test_case.get('id', 'unknown')}")
                test_case["steps"] = [test_case["steps"]] if test_case["steps"] else []

            # 验证预期结果是否为列表
            if not isinstance(test_case["expected_results"], list):
                logger.warning(f"测试用例预期结果不是列表: {test_case.get('id', 'unknown')}")
                test_case["expected_results"] = [test_case["expected_results"]] if test_case["expected_results"] else []

            return True
        except Exception as e:
            logger.error(f"验证测试用例错误: {str(e)}")
            return False

    def _parse_string_feedback(self, feedback: str) -> Dict:
        """从字符串格式的反馈中提取结构化的审查评论。"""
        review_comments = {
            "completeness": [],
            "clarity": [],
            "executability": [],
            "boundary_cases": [],
            "error_scenarios": []
        }

        if not feedback:
            return review_comments

        # 解析反馈内容
        feedback_sections = [line.strip() for line in feedback.split('\n') if line.strip()]
        current_section = None

        # 提取各个方面的改进建议
        for line in feedback_sections:
            # 识别章节标题
            section_mapping = {
                '1. 完整性': 'completeness',
                '2. 清晰度': 'clarity',
                '3. 可执行性': 'executability',
                '4. 边界情况': 'boundary_cases',
                '5. 错误场景': 'error_scenarios'
            }

            for title, section in section_mapping.items():
                if title in line:
                    current_section = section
                    break

            # 提取建议内容
            if current_section and (line.startswith('-') or line.startswith('•')):
                content = line[1:].strip()
                if content:  # 确保内容不为空
                    review_comments[current_section].append(content)

        return review_comments

    def _generate_feature_test_cases(self, feature: str, feature_items: List[Dict], priorities: List[Dict],
                                     test_approach: Dict) -> List[Dict]:
        """为单个功能点生成测试用例。"""
        try:
            user_proxy = autogen.UserProxyAgent(
                name="user_proxy",
                system_message="测试策略提供者",
                human_input_mode="NEVER",
                code_execution_config={"use_docker": False}
            )

            # 构建功能点特定的提示信息
            coverage_info = f"\n功能点 '{feature}' 的测试覆盖:\n"
            for item in feature_items:
                test_type = item.get('test_type', '')
                coverage_info += f"- 测试类型: {test_type}\n"

            # 构建优先级信息
            priority_info = "\n测试优先级:\n"
            for item in priorities:
                priority_info += f"- {item.get('level', '')}: {item.get('description', '')}\n"

            # 构建测试方法信息
            approach_info = "\n测试方法:\n"
            if isinstance(test_approach, dict):
                for key, value in test_approach.items():
                    if isinstance(value, list):
                        approach_info += f"- {key}: {', '.join(value)}\n"
                    else:
                        approach_info += f"- {key}: {value}\n"

            # 生成功能点特定的测试用例
            prompt = f"""请为功能点 '{feature}' 创建详细的测试用例：

            {approach_info}
            {coverage_info}
            {priority_info}

            请确保每个测试用例都明确针对功能点 '{feature}'，并遵循定义的优先级策略。
            测试用例的优先级必须使用测试优先级中定义的级别（如P0、P1等）。
            测试用例的类别应该与测试覆盖矩阵中的测试类型相对应。

            重要：
            + 必须覆盖功能点 '{feature}' 的所有测试类型
            + 每个测试类型至少创建一个测试用例

            对每个测试用例，请提供：
            1. 用例ID（格式：TC-{feature}-XXX，例如TC-文件上传-001）
            2. 标题（必须包含功能点名称）
            3. 描述（详细说明测试的目的和范围）
            4. 前置条件
            5. 测试步骤
            6. 预期结果
            7. 优先级（使用上述优先级定义）
            8. 类别（对应测试覆盖矩阵中的测试类型）

            请直接提供测试用例，无需等待进一步确认。"""

            # 调用大模型生成测试用例
            user_proxy.initiate_chat(
                self.agent,
                message=prompt,
                max_turns=1
            )

            # 解析测试用例
            last_message = self.agent.last_message(user_proxy)
            if not last_message:
                logger.warning(f"未能获取到功能点 '{feature}' 的测试用例生成结果")
                return []

            test_cases = self._parse_test_cases(last_message)

            # 如果解析结果为空，尝试重新生成一次
            if not test_cases:
                logger.warning(f"功能点 '{feature}' 的第一次测试用例生成为空，尝试重新生成")

                # 构建更明确的提示
                retry_prompt = f"""请重新为功能点 '{feature}' 创建测试用例，确保严格按照要求生成。

                必须为功能点 '{feature}' 的每个测试类型创建至少一个测试用例：
                {coverage_info}

                测试用例必须使用以下优先级：
                {priority_info}

                每个测试用例必须包含：ID、标题、描述、前置条件、测试步骤、预期结果、优先级和类别。
                ID格式必须为TC{feature}XXX，标题必须包含功能点名称 '{feature}'。
                优先级必须使用P0、P1等格式，类别必须与测试类型对应。

                请以JSON格式返回测试用例，确保格式正确。"""

                # 重新尝试生成测试用例，使用更明确的JSON格式要求
                retry_prompt += "\n\n请务必以以下格式返回JSON：\n``json\n{\n  \"test_cases\": [\n    {\n      \"id\": \"TC车牌识别001\",\n      \"title\": \"车牌识别功能验证\",\n      \"description\": \"验证车牌识别功能的准确性和稳定性\",\n      \"preconditions\": [\"前置条件1\", \"前置条件2\"],\n      \"steps\": [\"步骤1\", \"步骤2\"],\n      \"expected_results\": [\"预期结果1\", \"预期结果2\"],\n      \"priority\": \"P0\",\n      \"category\": \"功能测试\"\n    }\n  ]\n}\n```\n\n请确保JSON格式正确，所有字段都存在且有效。"

                user_proxy.initiate_chat(
                    self.agent,
                    message=retry_prompt,
                    max_turns=1
                )

                # 再次解析测试用例
                last_message = self.agent.last_message(user_proxy)
                if not last_message:
                    logger.warning(f"重试时未能获取到功能点 '{feature}' 的测试用例生成结果")
                    return []

                # 确保last_message是字符串类型
                message_content = last_message
                if isinstance(message_content, dict) and 'content' in message_content:
                    message_content = message_content['content']

                if isinstance(message_content, str):
                    logger.info(f"重试生成的消息内容: {message_content[:200]}...")
                else:
                    logger.info(f"重试生成的消息内容: {str(message_content)[:200]}...")
                test_cases = self._parse_test_cases(last_message)

                # 如果仍然为空，尝试手动构建一个基本测试用例
                if not test_cases:
                    logger.error(f"功能点 '{feature}' 的生成测试用例失败，返回空列表")
                    return []

            # 确保所有测试用例都包含功能点名称
            for tc in test_cases:
                if feature.lower() not in tc.get('title', '').lower():
                    tc['title'] = f"{feature} - {tc['title']}"

            logger.info(f"成功为功能点 '{feature}' 生成 {len(test_cases)} 个测试用例")
            return test_cases

        except Exception as e:
            logger.error(f"为功能点 '{feature}' 生成测试用例时出错: {str(e)}")
            return []

    def _validate_coverage(self, test_cases: List[Dict], coverage_matrix: List[Dict]) -> None:
        """验证测试用例是否与测试覆盖矩阵对应。"""
        if not coverage_matrix or not test_cases:
            return

        # 提取功能点和测试类型的映射关系
        feature_type_map = {}
        for item in coverage_matrix:
            feature = item.get('feature', '')
            test_type = item.get('test_type', '')
            if feature not in feature_type_map:
                feature_type_map[feature] = set()
            if isinstance(test_type, str):
                for t in test_type.split(','):
                    feature_type_map[feature].add(t.strip())
            else:
                feature_type_map[feature].add(test_type)

        # 检查每个功能点是否被测试用例覆盖
        covered_features = set()
        for tc in test_cases:
            # 从测试用例标题中提取可能的功能点
            title = tc.get('title', '').lower()
            for feature in feature_type_map.keys():
                if feature.lower() in title:
                    covered_features.add(feature)

        # 记录覆盖情况
        logger.info(f"测试覆盖矩阵测试点总数: {len(feature_type_map)}")
        logger.info(f"已覆盖测试点数量: {len(covered_features)}")

        # 检查是否有未覆盖的功能点
        uncovered = set(feature_type_map.keys()) - covered_features
        if uncovered:
            logger.warning(f"以下测试点未被测试用例覆盖: {uncovered}")

            # 如果覆盖率低于80%，记录警告
            coverage_rate = len(covered_features) / len(feature_type_map) if feature_type_map else 1.0
            if coverage_rate < 0.8:
                logger.warning(f"测试用例覆盖率过低: {coverage_rate:.2%}，建议增加测试用例数量")

    def _get_current_timestamp(self) -> str:
        """获取当前时间戳。"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _delete_feature_test_case_files(self, feature_count: int) -> None:
        """删除临时的功能点测试用例文件。

        Args:
            feature_count: 功能点的数量
        """
        try:
            import os

            for i in range(1, feature_count + 1):
                file_path = os.path.join(self.agent_io.output_dir, f"test_case_writer_feature_{i}_result.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"已删除临时测试用例文件: {file_path}")

            logger.info("所有临时测试用例文件已清理完毕")
        except Exception as e:
            logger.error(f"删除临时测试用例文件时出错: {str(e)}")

    def delete_improved_batch_files(self) -> None:
        """删除测试用例改进过程中生成的临时批次文件。
        在测试用例导出到Excel后调用此函数清理中间文件。
        """
        try:
            import os
            import glob

            # 查找所有改进批次的临时文件
            pattern = os.path.join(self.agent_io.output_dir, "test_case_writer_improved_batch_*_result.json")
            batch_files = glob.glob(pattern)

            # 删除找到的所有批次文件
            for file_path in batch_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"已删除临时改进批次文件: {file_path}")

            if batch_files:
                logger.info(f"所有临时改进批次文件已清理完毕，共删除 {len(batch_files)} 个文件")
            else:
                logger.info("未找到需要清理的临时改进批次文件")
        except Exception as e:
            logger.error(f"删除临时改进批次文件时出错: {str(e)}")

    def _generate_feature_test_cases_concurrent(self, feature_groups: Dict, priorities: List[Dict],
                                                test_approach: Dict) -> List[Dict]:
        """使用并发方式为多个功能点生成测试用例。
        根据concurrent_workers参数控制并发数。
        """
        if not feature_groups:
            logger.warning("没有功能点需要处理")
            return []

        # 确定批次大小和批次数
        total_features = len(feature_groups)
        # 根据并发工作线程数确定批次数，每个工作线程至少处理一个批次
        num_batches = min(total_features, self.concurrent_workers * 2)  # 每个工作线程处理约2个批次
        batch_size = max(1, total_features // num_batches)  # 确保每批至少有1个功能点

        # 将功能点分成批次
        feature_items = list(feature_groups.items())
        batches = [feature_items[i:i + batch_size] for i in range(0, total_features, batch_size)]
        logger.info(
            f"将{total_features}个功能点分成{len(batches)}批进行处理，每批约{batch_size}个功能点，并发工作线程数: {self.concurrent_workers}")

        # 使用线程池并发处理功能点
        all_test_cases = []
        import concurrent.futures

        # 定义批处理函数
        def process_batch(batch_index, batch_features):
            logger.info(f"开始处理第{batch_index + 1}批功能点，共{len(batch_features)}个")
            batch_test_cases = []

            for i, (feature, items) in enumerate(batch_features):
                logger.info(
                    f"开始为功能点 '{feature}' 生成测试用例 (批次{batch_index + 1}，功能点{i + 1}/{len(batch_features)})")

                # 为单个功能点生成测试用例
                feature_test_cases = self._generate_feature_test_cases(
                    feature=feature,
                    feature_items=items,
                    priorities=priorities,
                    test_approach=test_approach
                )

                if feature_test_cases:
                    batch_test_cases.extend(feature_test_cases)
                    logger.info(f"功能点 '{feature}' 生成了 {len(feature_test_cases)} 个测试用例")

                    # 保存中间结果，防止因超时丢失数据
                    feature_index = batch_index * batch_size + i + 1
                    temp_result = {
                        "test_cases": feature_test_cases,  # 只保存当前功能点的测试用例
                        "generation_date": self._get_current_timestamp(),
                        "generation_status": "in_progress",
                        "feature_progress": f"{feature_index}/{total_features}"
                    }
                    try:
                        self.agent_io.save_result(f"test_case_writer_feature_{feature_index}", temp_result)
                        logger.info(f"已保存功能点 '{feature}' 的测试用例生成结果")
                    except Exception as e:
                        logger.error(f"保存功能点 '{feature}' 的测试用例生成结果时出错: {str(e)}")
                else:
                    logger.warning(f"功能点 '{feature}' 未能生成有效的测试用例")

            logger.info(f"第{batch_index + 1}批功能点处理完成，共生成{len(batch_test_cases)}个测试用例")
            return batch_test_cases

        # 使用线程池执行器并发处理批次
        batch_results = []  # 初始化为空列表，而不是[None] * len(batches)
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {executor.submit(process_batch, i, batch): i for i, batch in enumerate(batches)}

            # 收集结果但不立即合并
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_index = future_to_batch[future]
                try:
                    batch_result = future.result()
                    # 确保batch_results有足够的元素
                    while len(batch_results) <= batch_index:
                        batch_results.append(None)
                    batch_results[batch_index] = batch_result  # 存储批次结果
                    logger.info(f"第{batch_index + 1}批测试用例处理完成并保存")
                except Exception as e:
                    logger.error(f"处理第{batch_index + 1}批测试用例时出错: {str(e)}")
                    # 如果处理失败，使用原始批次
                    # 确保batch_results有足够的元素
                    while len(batch_results) <= batch_index:
                        batch_results.append(None)
                    batch_results[batch_index] = batches[batch_index]

        # 所有批次处理完成后，统一合并结果
        for batch_result in batch_results:
            if batch_result:
                all_test_cases.extend(batch_result)
        logger.info(f"所有批次测试用例结果已合并完成")

        logger.info(f"所有测试用例处理完成，共生成{len(all_test_cases)}个测试用例")
        return all_test_cases

    def _merge_feature_test_cases(self, feature_count: int) -> None:
        """合并所有功能点的测试用例文件。

        Args:
            feature_count: 功能点的数量
        """
        try:
            all_test_cases = []

            # 读取每个功能点的测试用例文件
            for i in range(1, feature_count + 1):
                feature_result = self.agent_io.load_result(f"test_case_writer_feature_{i}")
                if feature_result and "test_cases" in feature_result:
                    all_test_cases.extend(feature_result["test_cases"])
                    logger.info(f"已加载功能点 {i} 的测试用例，共 {len(feature_result['test_cases'])} 个")
                else:
                    logger.warning(f"未能加载功能点 {i} 的测试用例")

            if all_test_cases:
                # 保存合并后的测试用例到最终文件
                final_result = {
                    "test_cases": all_test_cases,
                    "generation_date": self._get_current_timestamp(),
                    "generation_status": "completed",
                    "feature_count": feature_count
                }
                self.agent_io.save_result("test_case_writer", final_result)
                logger.info(f"已合并所有功能点的测试用例，共 {len(all_test_cases)} 个")

                # 删除临时的功能点测试用例文件
                self._delete_feature_test_case_files(feature_count)
            else:
                logger.warning("未能合并任何测试用例")

        except Exception as e:
            logger.error(f"合并功能点测试用例时出错: {str(e)}")

    def improve_test_cases(self, test_cases: List[Dict], qa_feedback: Union[str, Dict]) -> List[Dict]:
        """根据质量保证团队的反馈改进测试用例。
        优化：将测试用例分批次进行改进，并使用并发处理方式提高效率，并发数由concurrent_workers参数控制。
        """
        try:
            # 参数验证
            if not test_cases or not isinstance(test_cases, list):
                logger.warning("无效的测试用例输入")
                return test_cases

            # 处理qa_feedback，确保review_comments是字典类型
            if isinstance(qa_feedback, str):
                review_comments = self._parse_string_feedback(qa_feedback)
                feedback_str = qa_feedback
            elif isinstance(qa_feedback, dict):
                review_comments = qa_feedback.get('review_comments', {})
                # 将字典转换为字符串
                feedback_str = json.dumps(qa_feedback, ensure_ascii=False, indent=2)
            elif isinstance(qa_feedback, list):
                # 如果是列表，直接使用
                review_comments = qa_feedback
                feedback_str = '\n'.join(qa_feedback) if all(
                    isinstance(item, str) for item in qa_feedback) else json.dumps(qa_feedback, ensure_ascii=False,
                                                                                   indent=2)
            else:
                logger.warning("无效的反馈格式")
                return test_cases

            if not review_comments and not feedback_str:
                logger.warning("未找到有效的反馈内容")
                return test_cases

            # 根据并发工作线程数决定使用并发还是顺序处理
            if self.concurrent_workers > 1:
                logger.info(f"使用并发方式处理测试用例改进，并发数: {self.concurrent_workers}")
                all_improved_cases = self._improve_test_cases_concurrent(test_cases, feedback_str, review_comments)
            else:
                logger.info("使用顺序方式处理测试用例改进")
                # 将测试用例分成10批进行处理，避免一次处理过多
                batch_size = max(1, len(test_cases) // 10)  # 确保至少每批1个用例
                batches = [test_cases[i:i + batch_size] for i in range(0, len(test_cases), batch_size)]
                logger.info(f"将{len(test_cases)}个测试用例分成{len(batches)}批进行处理，每批约{batch_size}个用例")

                # 分批处理测试用例
                all_improved_cases = []
                for i, batch in enumerate(batches):
                    logger.info(f"开始处理第{i + 1}批测试用例，共{len(batch)}个")

                    # 使用大模型改进当前批次的测试用例
                    batch_improved_cases = self._improve_with_llm(batch, feedback_str)

                    # 如果改进失败，使用原始测试用例
                    if not batch_improved_cases:
                        logger.warning(f"第{i + 1}批测试用例改进失败，使用原始测试用例")
                        all_improved_cases.extend(batch)
                    else:
                        all_improved_cases.extend(batch_improved_cases)
                        logger.info(f"第{i + 1}批测试用例改进完成")

                    # 保存中间结果，防止因超时丢失数据
                    temp_result = {
                        "test_cases": batch_improved_cases,  # 只保存当前批次的结果，而不是累积结果
                        "review_comments": review_comments,
                        "review_date": self._get_current_timestamp(),
                        "review_status": "in_progress",
                        "batch_progress": f"{i + 1}/{len(batches)}"
                    }
                    try:
                        self.agent_io.save_result(f"test_case_writer_improved_batch_{i + 1}", temp_result)
                        logger.info(f"已保存第{i + 1}批改进后的测试用例")
                    except Exception as e:
                        logger.error(f"保存第{i + 1}批改进后的测试用例时出错: {str(e)}")

            # 如果没有改进任何测试用例，返回原始测试用例
            if not all_improved_cases:
                logger.warning("所有批次的测试用例改进都失败，返回原始测试用例")
                return test_cases

            # 保存改进后的测试用例
            self.last_cases = all_improved_cases
            self.agent_io.save_result("test_case_writer", {"test_cases": all_improved_cases})

            logger.info(f"测试用例改进完成，共改进 {len(all_improved_cases)} 个测试用例")
            return all_improved_cases

        except Exception as e:
            logger.error(f"改进测试用例错误: {str(e)}")
            return test_cases

    def _improve_test_cases_concurrent(self, test_cases: List[Dict], feedback_str: str, review_comments: Dict) -> List[
        Dict]:
        """使用并发方式处理测试用例改进。
        根据concurrent_workers参数控制并发数。
        """
        if not test_cases:
            logger.warning("没有测试用例需要处理")
            return []

        # 确定批次大小和批次数
        total_cases = len(test_cases)
        # 根据并发工作线程数确定批次数，每个工作线程至少处理一个批次
        num_batches = min(total_cases, self.concurrent_workers * 2)  # 每个工作线程处理约2个批次
        batch_size = max(1, total_cases // num_batches)  # 确保每批至少有1个用例

        batches = [test_cases[i:i + batch_size] for i in range(0, total_cases, batch_size)]
        logger.info(
            f"将{total_cases}个测试用例分成{len(batches)}批进行处理，每批约{batch_size}个用例，并发工作线程数: {self.concurrent_workers}")

        # 使用线程池并发处理测试用例
        all_improved_cases = []
        import concurrent.futures

        # 定义批处理函数
        def process_improvement_batch(batch_index, batch_cases):
            logger.info(f"开始处理第{batch_index + 1}批测试用例，共{len(batch_cases)}个")

            # 使用大模型改进当前批次的测试用例
            batch_improved_cases = self._improve_with_llm(batch_cases, feedback_str)

            # 如果改进失败，使用原始测试用例
            if not batch_improved_cases:
                logger.warning(f"第{batch_index + 1}批测试用例改进失败，使用原始测试用例")
                batch_improved_cases = batch_cases
            else:
                logger.info(f"第{batch_index + 1}批测试用例改进完成")

            # 保存中间结果，防止因超时丢失数据
            temp_result = {
                "test_cases": batch_improved_cases,  # 只保存当前批次的结果，而不是累积结果
                "review_comments": review_comments,
                "review_date": self._get_current_timestamp(),
                "review_status": "in_progress",
                "batch_progress": f"{batch_index + 1}/{len(batches)}"
            }
            try:
                self.agent_io.save_result(f"test_case_writer_improved_batch_{batch_index + 1}", temp_result)
                logger.info(f"已保存第{batch_index + 1}批改进后的测试用例")
            except Exception as e:
                logger.error(f"保存第{batch_index + 1}批改进后的测试用例时出错: {str(e)}")

            logger.info(f"第{batch_index + 1}批测试用例处理完成")
            return batch_improved_cases

        # 使用线程池执行器并发处理批次
        batch_results: List[List[Dict] | None] = [None] * len(batches)  # 预先分配结果列表
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrent_workers) as executor:
            # 提交所有批次任务
            future_to_batch = {executor.submit(process_improvement_batch, i, batch): i for i, batch in
                               enumerate(batches)}

            # 收集结果但不立即合并
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_index = future_to_batch[future]
                try:
                    batch_result = future.result()
                    batch_results[batch_index] = batch_result  # 存储批次结果
                    logger.info(f"第{batch_index + 1}批测试用例处理完成并保存")
                except Exception as e:
                    logger.error(f"处理第{batch_index + 1}批测试用例时出错: {str(e)}")

        # 所有批次处理完成后，统一合并结果
        for batch_result in batch_results:
            if batch_result:
                all_improved_cases.extend(batch_result)
        logger.info(f"所有批次测试用例结果已合并完成")

        logger.info(f"所有测试用例处理完成，共改进{len(all_improved_cases)}个测试用例")
        return all_improved_cases

    def _improve_with_llm(self, test_cases: List[Dict], feedback: str) -> List[Dict]:
        """使用大模型改进测试用例。"""
        try:
            # 创建用户代理
            user_proxy = autogen.UserProxyAgent(
                name="user_proxy",
                system_message="测试用例和反馈提供者",
                human_input_mode="NEVER",
                code_execution_config={"use_docker": False}
            )

            # 将测试用例转换为JSON字符串
            test_cases_json = json.dumps({"test_cases": test_cases}, ensure_ascii=False, indent=2)

            # 构建提示信息
            prompt = f"""请根据以下质量审查反馈，改进已有用例、补充缺失测试用例：

            原始测试用例：
            {test_cases_json}

            质量审查反馈：
            {feedback}

            请根据反馈改进现有测试用例并添加新的测试用例，确保：
            1. 完整性 - 所有必要字段都存在且有意义
            2. 清晰度 - 标题、步骤和预期结果描述清晰
            3. 可执行性 - 每个步骤都有对应的预期结果
            4. 边界情况 - 考虑边界条件
            5. 错误场景 - 考虑可能的错误情况
            6. 出现用例未覆盖的场景和未考虑到的边界条件，务必添加新的测试用例

            要求：
            1. 保留并改进所有原始测试用例
            2. 根据审查意见添加新的测试用例
            3. 新增的测试用例必须遵循相同的格式和结构
            4. 为每个新增的测试用例分配唯一的ID

            请返回完整的测试用例列表，包含改进后的原有用例和新增的用例。
            返回格式必须是JSON，保持与原始测试用例相同的结构。
            请直接返回完整的JSON格式测试用例，不要添加任何额外的解释。"""

            # 最大重试次数
            max_retries = 3
            improved_cases = []

            for attempt in range(max_retries):
                try:
                    # 调用大模型改进测试用例
                    user_proxy.initiate_chat(
                        self.agent,
                        message=prompt,
                        max_turns=1  # 限制对话轮次为1，避免死循环
                    )

                    # 获取大模型的响应
                    response = None
                    msg_list = user_proxy.chat_messages[self.agent]
                    print(f'debug:{type(msg_list)}')
                    response = msg_list[-1]['content']

                    # 检查响应是否为空
                    if not response:
                        logger.warning(f"尝试 {attempt + 1}/{max_retries}: 未能获取到test_case_writer的响应")
                        continue

                    logger.debug(f"尝试 {attempt + 1}/{max_retries}: 获取到的响应内容: {response[:100]}...")

                    # 解析响应
                    improved_cases = self._parse_llm_response(response)

                    # 验证改进后的测试用例
                    if not improved_cases:
                        logger.warning(f"尝试 {attempt + 1}/{max_retries}: 大模型未返回有效的测试用例，将重试")
                        continue

                    # 确保改进后的测试用例包含所有必需字段
                    validated_cases = []
                    for case in improved_cases:
                        if self._validate_test_case(case):
                            validated_cases.append(case)
                        else:
                            logger.warning(f"改进后的测试用例验证失败: {case.get('id', 'unknown')}")

                    if not validated_cases:
                        logger.warning(f"尝试 {attempt + 1}/{max_retries}: 所有改进后的测试用例验证失败，将重试")
                        continue

                    # 如果成功获取并验证了测试用例，跳出重试循环
                    logger.info(f"成功使用大模型改进 {len(validated_cases)} 个测试用例")
                    return validated_cases

                except Exception as e:
                    logger.error(f"尝试 {attempt + 1}/{max_retries}: 使用大模型改进测试用例错误: {str(e)}")

            # 如果所有重试都失败，返回原始测试用例
            if not improved_cases:
                logger.warning("所有重试都失败，返回原始测试用例")
                return test_cases

            return improved_cases

        except Exception as e:
            logger.error(f"使用大模型改进测试用例错误: {str(e)}")
            return test_cases

    def _parse_llm_response(self, response) -> List[Dict]:
        """解析大模型的响应，提取改进后的测试用例。"""
        try:
            # 检查response类型
            if isinstance(response, dict):
                print(f'改进测试用例的响应debug: {response}')
                # 如果是字典，尝试从content字段获取内容
                if 'content' in response:
                    response = response['content']
                else:
                    logger.error(f"无法从字典中提取响应内容: {response}")
                    return []

            # 确保response是字符串
            if not isinstance(response, str):
                logger.error(f"响应不是字符串类型: {type(response)}")
                return []

            # 使用统一的JSON解析器
            json_data = self.json_parser.parse(response, "test_case_improvement")

            if json_data:
                if 'test_cases' in json_data and isinstance(json_data['test_cases'], list):
                    logger.info(f"成功从JSON响应中解析出 {len(json_data['test_cases'])} 个改进后的测试用例")
                    return json_data['test_cases']
                elif isinstance(json_data, list):
                    logger.info(f"成功从JSON响应中解析出 {len(json_data)} 个改进后的测试用例")
                    return json_data

            logger.warning("无法从响应中提取有效的测试用例")
            return []

        except Exception as e:
            logger.error(f"解析大模型响应错误: {str(e)}")
            return []
