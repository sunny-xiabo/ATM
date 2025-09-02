"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: export_service.py
# @Date: 2025/8/27 11:41
"""
import re

import logging
from pathlib import Path
from typing import List
import pandas as pd
import os
from ..models.template import Template


logger = logging.getLogger(__name__)


class ExportService:
    """
        将测试用例输出到Excel格式的服务
    """

    def __init__(self):
        self.supported_formats = ['.xlsx']
        self.max_file_size_mb = 50  # 最大文件大小限制(MB)

    def _clean_text_data(self, text: str) -> str:
        """清理文本数据，移除emoji、null字节和其他特殊字符"""
        if not isinstance(text, str):
            return str(text) if text is not None else ""

        # 移除null字节
        text = text.replace('\x00', '')

        # 移除emoji和其他特殊Unicode字符
        # 保留基本的中文、英文、数字和常用标点符号
        text = re.sub(
            r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,!?;:()\[\]{}\-_+=<>/"\'\\|@#$%^&*~`，。！？；：（）【】｛｝—＋＝＜＞／""''＼｜＠＃＄％＾＆＊～｀\n\r\t]',
            '', text)

        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)

        # 移除开头和结尾的空白
        text = text.strip()

        return text

    def _clean_list_data(self, data_list: List) -> List:
        """清理列表数据"""
        if not isinstance(data_list, list):
            return []

        cleaned_list = []
        for item in data_list:
            if isinstance(item, str):
                cleaned_item = self._clean_text_data(item)
                if cleaned_item:  # 只添加非空项
                    cleaned_list.append(cleaned_item)
            else:
                cleaned_list.append(str(item))

        return cleaned_list

    async def export_to_excel(self,
                              test_cases: List,
                              template: Template,
                              output_path: str) -> str:
        try:
            # 验证输出路径
            path = Path(output_path)
            self._validate_output_path(path)

            # 转换测试用例到DataFrame
            df = self._convert_to_dataframe(test_cases, template)

            # 应用模板样式
            styled_df = self._apply_template_style(df, template)

            # 将DataFrame导出到Excel
            self._save_to_excel(styled_df, path, template)

            # 验证文件大小
            self._validate_file_size(path)

            return str(path)


        except Exception as e:
            logger.error(f"导出测试用例到Excel失败：{str(e)}")
            raise

    def _validate_output_path(self, path: Path):
        """
        验证输出路径的有效性
        :param path:
        :return:
        """
        # 确保路径有扩展名，如果没有则添加默认的.xlsx扩展名
        if not path.suffix:
            path = Path(str(path) + '.xlsx')
            logger.info(f"添加默认扩展名.xlsx到输出路径：{path}")

        # 检查文件格式
        if path.suffix not in self.supported_formats:
            logger.warning(f"文件格式不支持：{path.suffix}, 将使用.xlsx格式")
            # 替换不支持的扩展名为.xlsx
            path = Path(str(path.with_suffix('')) + '.xlsx')

        # 检查目录是否已存在
        if not path.parent.exists():
            raise ValueError(f"输出路径的父目录不存在：{path.parent}")

        # 检查目录写入权限
        if not os.access(path.parent, os.W_OK):
            raise ValueError(f"输出路径的父目录不可写：{path.parent}")

        # 如果文件已存在，检查是否可写
        if path.exists() and not os.access(path, os.W_OK):
            raise ValueError(f"文件没有写入权限：{path}")

    def _validate_file_size(self, path: Path):
        """
        验证导出文件大小
        :param path:
        :return:
        """
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            path.unlink()  # 删除超大文件
            raise ValueError(f"生成的文件大小({file_size_mb:.2f} MB)超过了最大限制({self.max_file_size_mb} MB)")

    def _convert_to_dataframe(self,
                              test_cases: List,
                              template: Template) -> pd.DataFrame:
        """
        将测试用例转换为DataFrame
        :param test_cases:
        :param template:
        :return:
        """
        data = []
        for test_case in test_cases:
            # 检查test_case是否为字典类型
            if isinstance(test_case, dict):
                # 如果是字典类型，直接使用字典的值
                row = {
                    'ID': test_case.get('id', ''),
                    'Title': test_case.get('title', ''),
                    'Description': test_case.get('description', ''),
                    'Preconditions': '\n'.join(test_case.get('preconditions', [])),
                    'Steps': '\n'.join(test_case.get('steps', [])),
                    'Expected Results': '\n'.join(test_case.get('expected_results', [])),
                    'Priority': test_case.get('priority', ''),
                    'Category': test_case.get('category', ''),
                    'Status': test_case.get('status', 'Draft'),
                    'Created At': test_case.get('created_at', ''),
                    'Updated At': test_case.get('updated_at', ''),
                    'Created By': test_case.get('created_by', ''),
                    'Last Updated By': test_case.get('last_updated_by', '')
                }
            else:
                # 如果是TestCase对象，使用对象的属性
                row = {
                    'ID': getattr(test_case, 'id', ''),
                    'Title': getattr(test_case, 'title', ''),
                    'Description': getattr(test_case, 'description', ''),
                    'Preconditions': '\n'.join(getattr(test_case, 'preconditions', [])),
                    'Steps': '\n'.join(getattr(test_case, 'steps', [])),
                    'Expected Results': '\n'.join(getattr(test_case, 'expected_results', [])),
                    'Priority': getattr(test_case, 'priority', ''),
                    'Category': getattr(test_case, 'category', ''),
                    'Status': getattr(test_case, 'status', 'Draft'),
                    'Created At': getattr(test_case, 'created_at', ''),
                    'Updated At': getattr(test_case, 'updated_at', ''),
                    'Created By': getattr(test_case, 'created_by', ''),
                    'Last Updated By': getattr(test_case, 'last_updated_by', '')
                }
            # 添加自定义字段
            for field in template.custom_fields:
                row[field] = getattr(test_case, field, '')
            data.append(row)

        return pd.DataFrame(data)

    def _apply_template_style(self,
                              df: pd.DataFrame,
                              template: Template) -> pd.DataFrame:
        """
        应用模板样式
        :param df:
        :param template:
        :return:
        """
        # 应用列宽 - 只转换为字符串类型，实际列宽在保存到Excel时应用
        for col, width in template.column_widths.items():
            if col in df.columns:
                df[col] = df[col].astype(str)

        # 应用条件格式
        for rule in template.conditional_formatting:
            if rule['column'] in df.columns and 'condition' in rule:
                try:
                    mask = df[rule['column']].str.contains(rule['condition'], na=False)

                    # 应用格式 - 根据format字段的值应用不同的格式
                    if 'format' in rule:
                        format_type = rule['format']
                        if format_type == 'highlight':
                            # 高亮显示
                            df.loc[mask, rule['column']] = f"*** {df.loc[mask, rule['column']]} ***"
                        elif format_type == 'prefix':
                            # 添加前缀
                            df.loc[mask, rule['column']] = f"! {df.loc[mask, rule['column']]}"
                        elif format_type == 'uppercase':
                            # 转换为大写
                            df.loc[mask, rule['column']] = df.loc[mask, rule['column']].str.upper()
                    else:
                        # 默认格式 - 如果没有指定format
                        df.loc[mask, rule['column']] = f"*** {df.loc[mask, rule['column']]} ***"
                except Exception as e:
                    logger.warning(f"Error applying conditional format: {str(e)}")

        return df

    def _save_to_excel(self,
                       df: pd.DataFrame,
                       path: Path,
                       template: Template | None = None):
        """
        将DataFrame导出到Excel
        :param df:
        :param path:
        :param template:
        :return:
        """
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Test Cases', index=False)

            # 应用列宽
            worksheet = writer.sheets['Test Cases']
            for idx, col in enumerate(df.columns):
                # 如果模板中定义了该列的宽度，则使用模板中定义的宽度
                if template and col in template.column_widths:
                    worksheet.column_dimensions[chr(65 + idx)].width = template.column_widths[col]
                else:
                    # 否则自动调整列宽
                    max_length = max(
                        df[col].astype(str).map(len).max(),
                        len(col)
                    )
                    # 设置最小和最大列宽
                    adjusted_width = min(max(max_length + 2, 10), 50)
                    worksheet.column_dimensions[chr(65 + idx)].width = adjusted_width
