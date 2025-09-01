"""
# -*- coding:utf-8 -*-
# @Author: Beck
# @File: document_prcessor.py
# @Date: 2025/8/26 16:38
"""
from pathlib import Path
import logging
from PyPDF2 import PdfReader
from docx import Document
import markdown


logger = logging.getLogger(__name__)


class DocumentProcessor:
    """不同文档类型处理"""
    SUPPORTED_FORMATS = {".pdf", ".docx", ".md", ".txt"}

    async def process_document(self, doc_path: Path) -> str:
        """
        处理输入文档并提取文本内容
        :param doc_path:
        :return:
        """
        try:
            path = Path(doc_path)
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {doc_path}")

            if path.suffix.lower() not in self.SUPPORTED_FORMATS:
                raise ValueError(f"不支持的文件格式: {path.suffix}")

            content = self._extract_content(path)
            return self._preprocess_content(content)
        except Exception as e:
            logger.error(f"处理{doc_path}文档时出错: {str(e)}")
            raise
    def _extract_content(self, file_path: Path) -> str:
        """
        从不同文件格式中提取文本内容
        :param file_path:
        :return:
        """
        if file_path.suffix == '.pdf':
            return self._extract_pdf_content(file_path)
        elif file_path.suffix == '.docx':
            return self._extract_docx_content(file_path)
        elif file_path.suffix == '.md':
            return self._extract_md_content(file_path)
        else:
            return self._extract_txt_content(file_path)


    def _extract_pdf_content(self,file_path: Path) -> str:
        """

        :param file_path:
        :return:
        """
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            return ' '.join(page.extract_text() for page in reader.pages)

    def _extract_docx_content(self, file_path: Path) -> str:
        """

        :param file_path:
        :return:
        """
        doc = Document(str(file_path))
        return ' '.join(paragraph.text for paragraph in doc.paragraphs)

    def _extract_md_content(self, file_path: Path) -> str:
        """

        :param file_path:
        :return:
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return markdown.markdown(content)

    def _extract_txt_content(self, file_path: Path) -> str:
        """

        :param file_path:
        :return:
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()


    def _preprocess_content(self, content: str) -> str:
        """
        预处理提取的内容以便更好地分析
        :param content:
        :return:
        """
        # 删除多余的空白并规范化行尾
        content = ' '.join(content.split())
        return content