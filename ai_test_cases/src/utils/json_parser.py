"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: json_parser.py
# @Date: 2025/9/2 09:49
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Union, List
from ast import literal_eval

logger = logging.getLogger(__name__)


class UnifiedJSONParser:
    """统一的JSON解析器，提供多种解析策略和错误处理机制"""

    def __init__(self):
        self.max_retries = 3
        self.similarity_threshold = 0.8
        self._context_strategies = {
            "test_case_improvement": [
                self._extract_json_block,  # 优先提取代码块
                self._direct_json_parse,  # 直接解析
                self._fix_json_format,  # 修复格式
                self._fix_json_aggressive,  # 激进修复
                self._extract_json_fallback,  # 备用提取
                self._extract_fallback_from_text
            ],
            "test_case_generation": [
                self._extract_json_block,  # 优先提取代码块
                self._direct_json_parse,  # 直接解析
                self._fix_json_format,  # 修复格式
                self._extract_json_fallback,  # 备用提取
                self._extract_fallback_from_text
            ],
            "test_design": [
                self._extract_json_block,  # 优先提取代码块
                self._direct_json_parse,  # 直接解析
                self._fix_json_format,  # 修复格式
                self._fix_json_aggressive,  # 激进修复
                self._extract_json_fallback,  # 备用提取
                self._extract_fallback_from_text
            ],
            "requirement_analysis": [
                self._extract_json_block,  # 优先提取代码块
                self._direct_json_parse,  # 直接解析
                self._fix_json_format,  # 修复格式
                self._extract_fallback_from_text
            ],
            "quality_assurance_review": [
                self._extract_json_block,  # 优先提取代码块
                self._direct_json_parse,  # 直接解析
                self._fix_json_format,  # 修复格式
                self._extract_json_fallback,  # 备用提取
                self._extract_fallback_from_text
            ]
        }
        # 默认策略顺序
        self._default_strategies = [
            self._extract_json_block,
            self._direct_json_parse,
            self._fix_json_format,
            self._fix_json_aggressive,
            self._extract_json_fallback,
            self._extract_fallback_from_text
        ]

    def parse(self, response: str, context: str = "unknown") -> Optional[Dict[str, Any]]:
        """
        解析AI响应中的JSON内容

        Args:
            response: AI的响应字符串
            context: 解析上下文，用于日志记录

        Returns:
            解析后的字典，如果解析失败返回None
        """
        if not response or not isinstance(response, str):
            logger.warning(f"[{context}] 响应为空或格式不正确")
            return None

        # 根据上下文选择最优策略顺序
        strategies = self._context_strategies.get(context, self._default_strategies)

        # 记录解析尝试
        last_error = None

        for i, strategy in enumerate(strategies):
            try:
                result = strategy(response)
                if result and isinstance(result, dict):
                    logger.info(f"[{context}] 使用策略 {i + 1} 成功解析JSON")
                    return result
            except Exception as e:
                last_error = str(e)
                logger.debug(f"[{context}] 策略 {i + 1} 失败: {str(e)}")
                continue

        # 如果所有策略都失败，尝试智能重试
        if context in ["test_case_improvement", "test_case_generation"]:
            logger.warning(f"[{context}] 所有策略失败，尝试智能重试")
            retry_result = self._smart_retry(response, context)
            if retry_result:
                return retry_result

        logger.error(f"[{context}] 所有JSON解析策略都失败了，最后错误: {last_error}")
        return None

    def _smart_retry(self, response: str, context: str) -> Optional[Dict[str, Any]]:
        """智能重试机制，针对特定上下文优化"""
        try:
            logger.info(f"[{context}] 开始智能重试，响应长度: {len(response)}")

            # 针对测试用例改进场景的特殊处理
            if context == "test_case_improvement":
                # 1. 尝试更宽松的JSON提取
                result = self._extract_test_cases_loosely(response)
                if result:
                    logger.info(f"[{context}] 智能重试成功 - 宽松提取")
                    return result

                # 2. 尝试从响应中提取任何可能的JSON片段
                result = self._extract_any_json_fragment(response)
                if result:
                    logger.info(f"[{context}] 智能重试成功 - 片段提取")
                    return result

                # 3. 尝试修复响应中的特殊字符和格式问题
                cleaned_response = self._deep_clean_response(response)
                if cleaned_response != response:
                    logger.info(f"[{context}] 尝试清理后的响应")
                    # 对清理后的响应重新尝试所有策略
                    for i, strategy in enumerate(self._default_strategies):
                        try:
                            result = strategy(cleaned_response)
                            if result and isinstance(result, dict):
                                logger.info(f"[{context}] 清理后使用策略 {i + 1} 成功解析JSON")
                                return result
                        except Exception as e:
                            logger.debug(f"[{context}] 清理后策略 {i + 1} 失败: {str(e)}")
                            continue

            # 4. 尝试修复常见的截断问题
            result = self._fix_truncated_json(response)
            if result:
                logger.info(f"[{context}] 修复截断JSON成功")
                return result

            # 5. 最后尝试：从文本中提取结构化信息
            if context == "test_case_improvement":
                result = self._extract_test_cases_from_text(response)
                if result:
                    logger.info(f"[{context}] 从文本提取测试用例成功")
                    return result

            logger.warning(f"[{context}] 智能重试失败，所有策略都无效")
            return None
        except Exception as e:
            logger.error(f"[{context}] 智能重试过程中出错: {str(e)}")
            return None

    def _extract_test_cases_loosely(self, response: str) -> Optional[Dict[str, Any]]:
        """宽松的测试用例提取策略"""
        try:
            # 查找包含test_cases的JSON片段
            test_cases_pattern = r'"test_cases"\s*:\s*\[(.*?)\]'
            match = re.search(test_cases_pattern, response, re.DOTALL)

            if match:
                # 构建完整的JSON结构
                test_cases_content = match.group(1)
                # 尝试修复和解析测试用例数组
                fixed_array = self._fix_test_cases_array(test_cases_content)
                if fixed_array:
                    return {"test_cases": fixed_array}

            return None
        except Exception:
            return None

    def _extract_any_json_fragment(self, response: str) -> Optional[Dict[str, Any]]:
        """提取任何可能的JSON片段"""
        try:
            # 查找任何可能的JSON对象或数组
            patterns = [
                r'(\{[^{}]*"[^{}]*"[^{}]*\})',  # 包含引号的JSON对象
                r'(\{[^{}]*\})',  # 简单JSON对象
                r'(\[[^\[\]]*\])',  # JSON数组
                r'(\{[^}]*\})',  # 嵌套JSON对象
            ]

            for pattern in patterns:
                matches = re.findall(pattern, response, re.DOTALL)
                for match in matches:
                    try:
                        # 尝试修复和解析
                        cleaned = self._clean_json_string(match)
                        result = json.loads(cleaned)
                        if isinstance(result, (dict, list)):
                            # 如果是数组，包装成字典
                            if isinstance(result, list):
                                return {"test_cases": result}
                            return result
                    except (json.JSONDecodeError, ValueError):
                        continue

            return None
        except Exception:
            return None

    def _fix_test_cases_array(self, array_content: str) -> Optional[List[Dict]]:
        """修复测试用例数组格式"""
        try:
            # 分割测试用例对象
            test_cases = []
            current_case = {}
            brace_count = 0
            start_pos = 0

            for i, char in enumerate(array_content):
                if char == '{':
                    if brace_count == 0:
                        start_pos = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # 提取一个完整的测试用例对象
                        case_str = array_content[start_pos:i + 1]
                        try:
                            # 尝试修复和解析
                            fixed_case = self._fix_single_test_case(case_str)
                            if fixed_case:
                                test_cases.append(fixed_case)
                        except:
                            continue

            return test_cases if test_cases else None
        except Exception:
            return None

    def _fix_single_test_case(self, case_str: str) -> Optional[Dict]:
        """修复单个测试用例的格式"""
        try:
            # 修复常见的格式问题
            fixed = case_str

            # 修复缺失的引号
            fixed = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)

            # 修复字符串值
            fixed = re.sub(r':\s*([^",\s][^,}]*?)(?=\s*[,}])', r': "\1"', fixed)

            # 修复数组值
            fixed = re.sub(r':\s*\[([^]]*?)\](?=\s*[,}])', r': [\1]', fixed)

            # 尝试解析
            return json.loads(fixed)
        except:
            return None

    def _fix_truncated_json(self, response: str) -> Optional[Dict[str, Any]]:
        """修复被截断的JSON"""
        try:
            # 查找最后一个完整的JSON对象
            brace_count = 0
            last_complete_pos = -1

            for i, char in enumerate(response):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_complete_pos = i

            if last_complete_pos > 0:
                # 提取到最后一个完整对象
                truncated_json = response[:last_complete_pos + 1]
                # 尝试修复和解析
                return self._fix_json_format(truncated_json)

            return None
        except Exception:
            return None

    def parse_json(self, json_str: str) -> Optional[Dict[str, Any]]:
        """
        直接解析JSON字符串

        Args:
            json_str: JSON字符串

        Returns:
            解析后的字典，如果解析失败返回None
        """
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None

    def fix_json_format(self, response: str) -> Optional[Dict[str, Any]]:
        """修复常见JSON格式问题 - 公共方法"""
        return self._fix_json_format(response)

    def fix_json_aggressive(self, response: str) -> Optional[Dict[str, Any]]:
        """更激进的JSON修复 - 公共方法"""
        return self._fix_json_aggressive(response)

    def extract_json_fallback(self, response: str) -> Optional[Dict[str, Any]]:
        """备用JSON提取策略 - 公共方法"""
        return self._extract_json_fallback(response)

    def build_structured_result(self, parsed_result: Dict[str, Any]) -> Dict[str, Any]:
        """构建结构化的测试策略结果 - 公共方法"""
        return {
            "test_approach": {
                "methodology": parsed_result.get("methodology", []),
                "tools": parsed_result.get("tools", []),
                "frameworks": parsed_result.get("frameworks", [])
            },
            "coverage_matrix": parsed_result.get("coverage_matrix", []),
            "priorities": parsed_result.get("priorities", []),
            "resource_estimation": parsed_result.get("resource_estimation", {
                "time": None,
                "personnel": None,
                "tools": [],
                "additional_resources": []
            })
        }

    def _direct_json_parse(self, response: str) -> Optional[Dict[str, Any]]:
        """直接JSON解析"""
        try:
            cleaned = response.strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_json_block(self, response: str) -> Optional[Dict[str, Any]]:
        """提取JSON代码块"""
        # 匹配 ```json ... ``` 或 ``` ... ```
        json_patterns = [
            r'```(?:json)?\s*(\{[\s\S]*?\})\s*```',
            r'```(?:json)?\s*(\[[\s\S]*?\])\s*```',
            r'(\{[\s\S]*?\})',
            r'(\[[\s\S]*?\])'
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1).strip()
                    # 清理可能的格式问题
                    json_str = self._clean_json_string(json_str)
                    return json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    continue

        return None

    def _clean_json_string(self, json_str: str) -> str:
        """清理JSON字符串中的常见问题"""
        try:
            # 移除可能的markdown标记
            json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
            json_str = re.sub(r'\s*```$', '', json_str)

            # 修复中文引号
            json_str = re.sub(r'[“”]', '"', json_str)
            json_str = re.sub(r"[‘’]", "'", json_str)

            # 修复换行符（保留在字符串值中的换行符）
            json_str = re.sub(r'(?<!\\)\n(?!")', '\\n', json_str)

            # 修复制表符
            json_str = re.sub(r'(?<!\\)\t', '\\t', json_str)

            # 修复末尾逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            return json_str.strip()
        except Exception:
            return json_str

    def _deep_clean_response(self, response: str) -> str:
        """深度清理响应中的特殊字符和格式问题"""
        try:
            cleaned = response

            # 1. 移除或替换可能导致JSON解析失败的特殊字符
            # 移除零宽字符
            cleaned = re.sub(r'[\u200b-\u200d\uFEFF]', '', cleaned)

            # 移除控制字符（保留换行符和制表符）
            cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)

            # 2. 修复常见的格式问题
            # 修复不完整的转义序列
            cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', cleaned)

            # 修复缺失的引号（在冒号后）
            cleaned = re.sub(r':\s*([^",\s][^,}]*?)(?=\s*[,}])', r': "\1"', cleaned)

            # 修复数组中的字符串值
            cleaned = re.sub(r'\[\s*([^",\s][^,\]]*?)\s*([,\]])', r'["\1"\2', cleaned)

            # 3. 尝试修复不完整的JSON结构
            # 查找最后一个完整的JSON对象
            brace_count = 0
            last_complete_pos = -1

            for i, char in enumerate(cleaned):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_complete_pos = i

            if last_complete_pos > 0:
                # 截取到最后一个完整对象
                cleaned = cleaned[:last_complete_pos + 1]

            return cleaned
        except Exception:
            return response

    def _fix_json_format(self, response: str) -> Optional[Dict[str, Any]]:
        """修复常见JSON格式问题"""
        try:
            # 清理响应，提取可能的JSON部分
            json_match = re.search(r'(\{[\s\S]*\})', response, re.DOTALL)
            if not json_match:
                return None

            json_str = json_match.group(1)

            # 使用统一的清理方法
            json_str = self._clean_json_string(json_str)

            # 修复缺失的引号
            json_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)

            # 修复字符串值（非数组中的值）
            json_str = re.sub(r':\s*([^",\s][^,}]*?)(?=\s*[,}])', r': "\1"', json_str)

            # 修复数组中的字符串值
            json_str = re.sub(r'\[\s*([^",\s][^,\]]*?)\s*([,\]])', r'["\1"\2', json_str)

            # 尝试解析
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                # 如果仍然失败，尝试更激进的修复
                return self._fix_json_aggressive(json_str)

        except (json.JSONDecodeError, ValueError):
            return None

    def _fix_json_aggressive(self, response: str) -> Optional[Dict[str, Any]]:
        """更激进的JSON修复"""
        try:
            # 提取可能的JSON结构
            json_match = re.search(r'(\{[\s\S]*\})', response, re.DOTALL)
            if not json_match:
                return None

            json_str = json_match.group(1)

            # 1. 修复缺失的逗号
            json_str = re.sub(r'(\w+)\s*(\w+)\s*:', r'\1",\2":', json_str)

            # 2. 修复不完整的字符串
            json_str = re.sub(r':\s*([^",\s]+)(?=\s*[,}])', r': "\1"', json_str)

            # 3. 修复数组格式
            json_str = re.sub(r'\[\s*([^,\]]+)\s*\]', r'["\1"]', json_str)

            # 4. 尝试使用ast.literal_eval作为备用方案
            try:
                parsed = literal_eval(json_str)
                if isinstance(parsed, dict):
                    return parsed
            except (ValueError, SyntaxError):
                pass

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return None

    def _extract_json_fallback(self, response: str) -> Optional[Dict[str, Any]]:
        """备用JSON提取策略"""
        try:
            # 查找任何可能的JSON结构
            patterns = [
                r'(\{[^{}]*"[^{}]*"[^{}]*\})',
                r'(\{[^{}]*\})',
                r'(\{[^}]*\})'
            ]

            for pattern in patterns:
                matches = re.findall(pattern, response)
                for match in matches:
                    try:
                        # 尝试修复和解析
                        fixed = self._fix_json_format(match)
                        if fixed:
                            return fixed
                    except:
                        continue

            return None
        except Exception:
            return None

    def _extract_fallback_from_text(self, response: str) -> Optional[Dict[str, Any]]:
        """从文本响应中提取结构化信息的备用方法"""
        try:
            # 初始化默认结构
            result = {
                "test_approach": {
                    "methodology": [],
                    "tools": [],
                    "frameworks": []
                },
                "coverage_matrix": [],
                "priorities": [],
                "resource_estimation": {
                    "time": None,
                    "personnel": None,
                    "tools": [],
                    "additional_resources": []
                }
            }

            # 提取功能需求
            func_reqs = re.findall(r'功能需求[：:]\s*(.+?)(?=\n|$)', response)
            if func_reqs:
                result['functional_requirements'] = [req.strip() for req in func_reqs]

            # 提取非功能需求
            nfr_reqs = re.findall(r'非功能需求[：:]\s*(.+?)(?=\n|$)', response)
            if nfr_reqs:
                result['non_functional_requirements'] = [req.strip() for req in nfr_reqs]

            # 提取测试场景
            scenarios = re.findall(r'测试场景[：:]\s*(.+?)(?=\n|$)', response)
            if scenarios:
                result['test_scenarios'] = [{'id': f'TS{i + 1:03d}', 'description': s.strip(), 'test_cases': []}
                                            for i, s in enumerate(scenarios)]

            # 提取风险领域
            risks = re.findall(r'风险[：:]\s*(.+?)(?=\n|$)', response)
            if risks:
                result['risk_areas'] = [risk.strip() for risk in risks]

            # 如果提取到了任何信息，返回结果
            if result:
                logger.info("从纯文本中提取到结构化信息")
                return result

            return None
        except Exception as e:
            logger.error(f"从文本提取结构化信息时出错: {str(e)}")
            return None

    def _extract_test_cases_from_text(self, response: str) -> Optional[Dict[str, Any]]:
        """从纯文本中提取测试用例信息"""
        try:
            test_cases = []

            # 查找包含测试用例信息的文本段落
            # 匹配包含ID、标题、步骤等关键词的段落
            test_case_patterns = [
                r'(?:测试用例|TestCase|TC)[\s\-\d]*[:：]\s*([^\n]+)',
                r'(?:ID|标识)[\s\-\d]*[:：]\s*([^\n]+)',
                r'(?:标题|Title)[\s\-\d]*[:：]\s*([^\n]+)',
                r'(?:步骤|Steps)[\s\-\d]*[:：]\s*([^\n]+)',
                r'(?:预期结果|Expected)[\s\-\d]*[:：]\s*([^\n]+)',
            ]

            # 提取可能的测试用例信息
            for pattern in test_case_patterns:
                matches = re.findall(pattern, response, re.IGNORECASE)
                for match in matches:
                    if match.strip():
                        # 构建简单的测试用例结构
                        test_case = {
                            "id": f"TC-{len(test_cases) + 1:03d}",
                            "title": match.strip(),
                            "preconditions": [],
                            "steps": [match.strip()],
                            "expected_results": ["验证功能正常"],
                            "priority": "P1",
                            "category": "功能测试"
                        }
                        test_cases.append(test_case)

            if test_cases:
                return {"test_cases": test_cases}

            return None
        except Exception as e:
            logger.debug(f"从文本提取测试用例时出错: {str(e)}")
            return None

    def validate_json_structure(self, data: Dict[str, Any], expected_keys: list) -> bool:
        """
        验证JSON结构是否符合预期

        Args:
            data: 解析后的数据
            expected_keys: 期望的键列表

        Returns:
            验证结果
        """
        if not isinstance(data, dict):
            return False

        for key in expected_keys:
            if key not in data:
                logger.warning(f"缺少必需的键: {key}")
                return False

        return True

    def get_parsing_statistics(self) -> Dict[str, Any]:
        """获取解析统计信息"""
        return {
            "total_parsing_attempts": getattr(self, '_total_attempts', 0),
            "successful_parses": getattr(self, '_successful_parses', 0),
            "failed_parses": getattr(self, '_failed_parses', 0),
            "success_rate": getattr(self, '_success_rate', 0.0)
        }
