import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from pathlib import Path
import configparser
import threading
import PyPDF2
import io
import jieba
import jieba.analyse
import pdfplumber
import logging
from datetime import datetime
from openai import OpenAI
import zipfile
import shutil
from typing import Dict, List, Any

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaperAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("智能计算机论文分析工具")
        self.root.geometry("800x600")
        
        # 加载配置
        self.config = configparser.ConfigParser()
        self.config_file = 'config.ini'
        self.load_config()
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # API设置区域
        self.create_api_settings()
        
        # 文件选择区域
        self.create_file_selection()
        
        # 结果显示区域
        self.create_results_area()
        
        # 设置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.config['API'] = {
                'key': '',
                'model': 'deepseek-ai/DeepSeek-V3'
            }
            self.save_config()
    
    def save_config(self):
        """保存配置到文件"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def create_api_settings(self):
        """创建API设置区域"""
        # API设置标题
        api_frame = ttk.LabelFrame(self.main_frame, text="DeepSeek API 设置", padding="10")
        api_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # API Key输入
        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W)
        self.api_key = ttk.Entry(api_frame, width=50, show="*")
        self.api_key.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.api_key.insert(0, self.config.get('API', 'key', fallback=''))
        
        # API Key说明
        ttk.Label(api_frame, text="从 https://cloud.siliconflow.cn/account/ak 获取", 
                 font=('Arial', 8)).grid(row=1, column=1, sticky=tk.W)
        
        # 模型选择
        ttk.Label(api_frame, text="模型选择:").grid(row=2, column=0, sticky=tk.W)
        self.model_var = tk.StringVar(value=self.config.get('API', 'model', fallback='deepseek-ai/DeepSeek-V3'))
        models = [
            'deepseek-ai/DeepSeek-V3',
            'deepseek-ai/DeepSeek-V2.5',
            'deepseek-ai/DeepSeek-V2',
            'deepseek-ai/DeepSeek-V1'
        ]
        self.model_combo = ttk.Combobox(api_frame, textvariable=self.model_var, values=models, state='readonly')
        self.model_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # 保存按钮
        ttk.Button(api_frame, text="保存设置", command=self.save_api_settings).grid(
            row=3, column=1, sticky=tk.E, pady=10)
        
    def create_file_selection(self):
        """创建文件选择区域"""
        file_frame = ttk.LabelFrame(self.main_frame, text="文件选择", padding="10")
        file_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        
        # 文件路径显示
        self.file_path = ttk.Entry(file_frame, width=50)
        self.file_path.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5)
        
        # 选择文件按钮
        ttk.Button(file_frame, text="选择PDF文件", command=self.select_file).grid(
            row=0, column=1, sticky=tk.E, padx=5)
        
        # 分析按钮
        ttk.Button(file_frame, text="分析论文", command=self.analyze_paper).grid(
            row=1, column=0, columnspan=2, sticky=tk.E, pady=10)
        
    def create_results_area(self):
        """创建结果显示区域"""
        results_frame = ttk.LabelFrame(self.main_frame, text="分析结果", padding="10")
        results_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # 基本信息显示
        self.info_text = tk.Text(results_frame, height=10, wrap=tk.WORD)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text['yscrollcommand'] = scrollbar.set
        
        # 下载按钮
        self.download_btn = ttk.Button(results_frame, text="下载思维导图", 
                                     command=self.download_mindmap, state='disabled')
        self.download_btn.grid(row=1, column=0, sticky=tk.E, pady=10)
        
        # 配置权重
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
    def save_api_settings(self):
        """保存API设置"""
        self.config['API'] = {
            'key': self.api_key.get(),
            'model': self.model_var.get()
        }
        self.save_config()
        messagebox.showinfo("成功", "API设置已保存")
        
    def select_file(self):
        """选择PDF文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf")]
        )
        if file_path:
            self.file_path.delete(0, tk.END)
            self.file_path.insert(0, file_path)
            
    def analyze_paper(self):
        """分析论文"""
        if not self.api_key.get():
            messagebox.showerror("错误", "请输入API Key")
            return
            
        if not self.file_path.get():
            messagebox.showerror("错误", "请选择PDF文件")
            return
            
        try:
            # 显示加载状态
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert(tk.END, "正在分析论文，请稍候...\n")
            self.root.update()

            # 读取PDF文件
            with open(self.file_path.get(), 'rb') as file:
                contents = file.read()

            # 提取文本
            text = self.extract_text_from_pdf(contents)
            if not text:
                raise Exception("无法从PDF中提取文本")

            # 检测语言
            language = self.detect_language(text)

            # 初始化 OpenAI 客户端
            client = OpenAI(
                api_key=self.api_key.get(),
                base_url="https://api.siliconflow.cn/v1"
            )

            # 提取关键词
            keywords = self.extract_keywords(text, language, client)

            # 分析论文结构
            structure = self.analyze_paper_structure(text, client)

            # 生成XMind文件
            filename = os.path.basename(self.file_path.get())
            xmind_path = self.create_xmind_file(structure, filename)

            # 显示结果
            self.info_text.delete('1.0', tk.END)
            self.info_text.insert(tk.END, f"文件名：{filename}\n")
            self.info_text.insert(tk.END, f"语言：{'中文' if language=='zh' else '英文'}\n")
            self.info_text.insert(tk.END, f"论文长度：{len(text)} 字符\n")
            self.info_text.insert(tk.END, f"关键词：{', '.join(keywords)}\n")

            # 启用下载按钮
            self.download_btn['state'] = 'normal'
            
            # 保存当前文件名用于下载
            self.current_filename = filename
            self.current_xmind_path = xmind_path
            
            messagebox.showinfo("成功", "论文分析完成")
            
        except Exception as e:
            messagebox.showerror("错误", f"分析论文时出错：{str(e)}")

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """从PDF中提取文本"""
        try:
            text = ""
            # 使用BytesIO读取PDF内容
            pdf_file = io.BytesIO(pdf_content)
            
            # 首先尝试使用PyPDF2
            try:
                reader = PyPDF2.PdfReader(pdf_file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            except Exception as e:
                logger.warning(f"PyPDF2提取失败，尝试使用pdfplumber: {str(e)}")
                
                # 如果PyPDF2失败，尝试使用pdfplumber
                pdf_file.seek(0)  # 重置文件指针
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
            
            return text.strip()
        except Exception as e:
            logger.error(f"PDF解析失败: {str(e)}")
            raise Exception(f"PDF解析失败: {str(e)}")

    def detect_language(self, text: str) -> str:
        """检测文本语言"""
        # 简单的语言检测：统计中文字符的比例
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return "zh" if chinese_chars / len(text) > 0.1 else "en"

    def extract_keywords(self, text: str, language: str, client: OpenAI) -> List[str]:
        """提取关键词"""
        try:
            if language == "zh":
                # 中文关键词提取
                keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=False)
                return keywords
            else:
                # 英文关键词提取
                response = client.chat.completions.create(
                    model=self.model_var.get(),
                    messages=[
                        {"role": "system", "content": "你是一个专业的计算机领域论文分析助手。请从论文中提取计算机领域的专业术语和关键词，包括但不限于：算法、框架、模型、技术、方法、工具等。每个关键词应该是计算机领域的专业术语。"},
                        {"role": "user", "content": f"请从以下论文中提取10个最重要的计算机领域专业术语作为关键词：\n\n{text}"}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                
                # 解析响应
                keywords_text = response.choices[0].message.content
                # 将响应文本转换为关键词列表
                keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
                return keywords[:10]  # 确保最多返回10个关键词
                
        except Exception as e:
            logger.error(f"提取关键词时出错: {str(e)}")
            return []

    def analyze_paper_structure(self, text: str, client: OpenAI) -> Dict[str, Any]:
        """分析论文结构"""
        try:
            # 使用 DeepSeek 分析论文结构
            response = client.chat.completions.create(
                model=self.model_var.get(),
                messages=[
                    {"role": "system", "content": """你是一个专业的论文分析助手。请详细分析论文的结构和内容。
请按照以下格式输出（注意：必须严格按照格式输出，不要添加额外的解释）：

第一章 xxx
- 内容点1
- 内容点2

1.1 xxx
- 内容点1
- 内容点2

1.2 xxx
- 内容点1
- 内容点2

第二章 xxx
- 内容点1
- 内容点2

2.1 xxx
- 内容点1
- 内容点2

...以此类推

要求：
1. 严格按照上述格式输出
2. 每个章节都要有内容要点
3. 内容要点要简洁明了
4. 必须包含二级标题（例如1.1、1.2等）
5. 所有内容要点必须以'-'开头"""},
                    {"role": "user", "content": f"请分析这篇论文的结构和内容：\n\n{text}"}
                ],
                temperature=0.3,
                max_tokens=4096
            )
            
            # 解析响应
            structure = response.choices[0].message.content
            
            # 将结构化内容转换为字典
            sections = {}
            current_chapter = None
            current_section = None
            current_content = []
            
            for line in structure.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                # 处理章节标题
                if line.startswith('第') and '章' in line:
                    if current_chapter and current_content:
                        if current_chapter not in sections:
                            sections[current_chapter] = {'content': [], 'subsections': {}}
                        sections[current_chapter]['content'] = current_content
                    current_chapter = line
                    current_section = None
                    current_content = []
                    if current_chapter not in sections:
                        sections[current_chapter] = {'content': [], 'subsections': {}}
                        
                # 处理小节标题
                elif line[0].isdigit() and '.' in line:
                    if current_section and current_content:
                        sections[current_chapter]['subsections'][current_section] = current_content
                    current_section = line
                    current_content = []
                    
                # 处理内容
                elif line.startswith('-'):
                    if current_section:
                        if current_chapter not in sections:
                            sections[current_chapter] = {'content': [], 'subsections': {}}
                        if current_section not in sections[current_chapter]['subsections']:
                            sections[current_chapter]['subsections'][current_section] = []
                        sections[current_chapter]['subsections'][current_section].append(line)
                    else:
                        if current_chapter not in sections:
                            sections[current_chapter] = {'content': [], 'subsections': {}}
                        sections[current_chapter]['content'].append(line)
            
            # 处理最后一个部分
            if current_section and current_content:
                sections[current_chapter]['subsections'][current_section] = current_content
            elif current_chapter and current_content:
                sections[current_chapter]['content'] = current_content
                
            return sections
        except Exception as e:
            logger.error(f"分析论文结构时出错: {str(e)}")
            return {}

    def create_xmind_file(self, structure: Dict[str, Any], filename: str) -> str:
        """创建XMind文件"""
        try:
            # 创建临时目录
            temp_dir = Path("temp_xmind")
            temp_dir.mkdir(exist_ok=True)
            (temp_dir / "Thumbnails").mkdir(exist_ok=True)
            
            # 准备XMind内容
            xmind_content = [{
                "rootTopic": {
                    "id": "root",
                    "title": f"{filename}论文结构",
                    "style": {
                        "background": "#1976D2",  # 深蓝色根节点
                        "color": "#FFFFFF"
                    },
                    "children": {
                        "attached": []
                    }
                },
                "id": "first-sheet",
                "class": "sheet",
                "title": "论文分析"
            }]
            
            # 添加章节
            for chapter, content in structure.items():
                chapter_node = self.create_node(chapter, content)
                xmind_content[0]["rootTopic"]["children"]["attached"].append(chapter_node)
            
            # 创建必要的文件
            manifest = {
                "file-entries": {
                    "content.json": {"full-path": "content.json", "media-type": "application/json"},
                    "metadata.json": {"full-path": "metadata.json", "media-type": "application/json"},
                    "Thumbnails/thumbnail.png": {"full-path": "Thumbnails/thumbnail.png", "media-type": "image/png"},
                    "manifest.json": {"full-path": "manifest.json", "media-type": "application/json"}
                }
            }
            
            metadata = {
                "creator": {
                    "name": "Paper Analysis Tool",
                    "version": "1.0"
                },
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat()
            }
            
            # 写入文件
            with open(temp_dir / "content.json", "w", encoding="utf-8") as f:
                json.dump(xmind_content, f, ensure_ascii=False, indent=2)
            
            with open(temp_dir / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
            
            with open(temp_dir / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # 创建空的缩略图文件
            with open(temp_dir / "Thumbnails" / "thumbnail.png", "wb") as f:
                f.write(b"")
            
            # 创建XMind文件
            output_dir = Path("static/mindmaps")
            output_dir.mkdir(exist_ok=True, parents=True)
            output_path = output_dir / f"{filename.replace('.pdf', '')}_structure.xmind"
            
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in temp_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(temp_dir))
            
            # 清理临时文件
            shutil.rmtree(temp_dir)
            
            return str(output_path)
        except Exception as e:
            logger.error(f"创建XMind文件失败: {str(e)}")
            raise Exception(f"创建XMind文件失败: {str(e)}")

    def create_node(self, title: str, content: Any, level: int = 1) -> dict:
        """创建节点"""
        THEME_COLORS = {
            "level1": {"default": "#1976D2"},  # 深蓝色
            "level2": {"default": "#2196F3"},  # 蓝色
            "level3": {"default": "#64B5F6"},  # 浅蓝色
            "content": {"background": "#E3F2FD", "color": "#000000"}  # 极浅蓝色背景，黑色文字
        }
        
        node = {
            "id": f"node_{hash(str(title))}",
            "title": title,
            "style": {
                "background": THEME_COLORS[f"level{level}"]["default"],
                "color": "#000000" if level > 1 else "#FFFFFF"
            },
            "children": {
                "attached": []
            }
        }
        
        if isinstance(content, dict):
            # 添加章节内容
            if content.get('content'):
                content_node = {
                    "id": f"content_{hash(str(content['content']))}",
                    "title": "\n".join(content['content']),
                    "style": THEME_COLORS["content"]
                }
                node["children"]["attached"].append(content_node)
            
            # 添加子章节
            for sub_title, sub_content in content.get('subsections', {}).items():
                sub_node = {
                    "id": f"node_{hash(str(sub_title))}",
                    "title": sub_title,
                    "style": {
                        "background": THEME_COLORS[f"level{level+1}"]["default"],
                        "color": "#000000"
                    },
                    "children": {
                        "attached": [{
                            "id": f"content_{hash(str(sub_content))}",
                            "title": "\n".join(sub_content),
                            "style": THEME_COLORS["content"]
                        }]
                    }
                }
                node["children"]["attached"].append(sub_node)
        elif isinstance(content, list):
            # 如果是列表，直接添加为内容
            content_node = {
                "id": f"content_{hash(str(content))}",
                "title": "\n".join(content),
                "style": THEME_COLORS["content"]
            }
            node["children"]["attached"].append(content_node)
        
        return node

    def download_mindmap(self):
        """下载思维导图"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".xmind",
                filetypes=[("XMind files", "*.xmind")],
                initialfile=f"{self.current_filename.replace('.pdf', '')}_structure.xmind"
            )
            
            if save_path:
                # 直接复制文件
                shutil.copy2(self.current_xmind_path, save_path)
                messagebox.showinfo("成功", "思维导图已下载")
                
        except Exception as e:
            messagebox.showerror("错误", f"下载思维导图时出错：{str(e)}")

def main():
    root = tk.Tk()
    app = PaperAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 