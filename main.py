from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import PyPDF2
import io
from typing import Dict, List, Any, Tuple
import uvicorn
import os
import jieba
import jieba.analyse
import pdfplumber
import logging
from datetime import datetime
import json
from openai import OpenAI
import zipfile
import shutil
from pathlib import Path
import graphviz
from xmindparser import xmind_to_dict
import tempfile

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置Graphviz路径
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Graphviz\bin"
graphviz.set_jupyter_format('png')

app = FastAPI(title="智能计算机论文分析工具")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key="sk-whehpfujdgqllqkphkqatygokgrumhsbrqnxzhdfaewaxciu",  # 请替换为您从 https://cloud.siliconflow.cn/account/ak 获取的 API key
    base_url="https://api.siliconflow.cn/v1"  # DeepSeek API 地址
)

# 定义主题颜色
THEME_COLORS = {
    # 第一层级颜色（主要章节）
    "level1": {
        "abstract": "#FF6B6B",      # 红色
        "introduction": "#4ECDC4",   # 青色
        "methodology": "#45B7D1",    # 蓝色
        "results": "#96CEB4",        # 绿色
        "discussion": "#FFEEAD",     # 黄色
        "conclusion": "#D4A5A5",     # 粉色
        "default": "#2196F3"         # 默认蓝色
    },
    # 第二层级颜色（子章节）
    "level2": {
        "background": "#E3F2FD",     # 浅蓝
        "research_background": "#FFE0B2",  # 浅橙
        "research_significance": "#F0F4C3", # 浅黄绿
        "research_objectives": "#B2DFDB",   # 浅青
        "data_collection": "#FFCCBC",      # 浅红
        "data_analysis": "#D1C4E9",       # 浅紫
        "experimental_design": "#C8E6C9",  # 浅绿
        "default": "#E1F5FE"         # 默认浅蓝
    },
    # 第三层级颜色（子子章节）
    "level3": {
        "background": "#F5F5F5",     # 浅灰
        "method_details": "#FFF3E0",  # 浅橙
        "analysis_process": "#F1F8E9", # 浅绿
        "results_details": "#E0F7FA", # 浅青
        "discussion_points": "#FFF8E1", # 浅黄
        "default": "#FAFAFA"         # 默认浅灰
    },
    # 内容节点颜色
    "content": {
        "background": "#FFFFFF",     # 白色
        "color": "#666666"          # 深灰色文字
    }
}

# 初始化模型
try:
    # 加载中文关键词词典
    logger.info("开始加载中文词典...")
    jieba.load_userdict("dict/computer_terms.txt")
    logger.info("中文词典加载完成")
    logger.info("初始化完成！")
except Exception as e:
    logger.error(f"初始化失败: {str(e)}")

def detect_language(text: str) -> str:
    """检测文本语言"""
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    total_chars = len(text)
    if total_chars == 0:
        return "unknown"
    chinese_ratio = chinese_chars / total_chars
    return "zh" if chinese_ratio > 0.3 else "en"

def extract_text_from_pdf(pdf_file: bytes) -> str:
    """从PDF文件中提取文本"""
    try:
        # 首先尝试使用PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # 如果提取的文本太少，尝试使用pdfplumber
        if len(text.strip()) < 100:
            with pdfplumber.open(io.BytesIO(pdf_file)) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
        
        return text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF解析失败: {str(e)}")

def analyze_paper_structure(text: str, client: OpenAI, model_name: str) -> Dict[str, Any]:
    """分析论文结构"""
    try:
        # 使用 DeepSeek 分析论文结构
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": """你是一个专业的论文分析助手。请详细分析论文的结构和内容。
请按照以下格式输出（注意：最后一级内容可根据论文内容提炼要点，以精炼专业的语言表述出来）：

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

def extract_keywords(text: str, language: str, client: OpenAI, model_name: str) -> List[str]:
    """提取关键词"""
    try:
        if language == "zh":
            # 中文关键词提取
            keywords = jieba.analyse.extract_tags(text, topK=10, withWeight=False)
            return keywords
        else:
            # 英文关键词提取（计算机领域专业术语）
            response = client.chat.completions.create(
                model=model_name,
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

def translate_to_chinese(text: str) -> str:
    """使用DeepSeek将英文翻译成中文"""
    try:
        messages = [
            {"role": "user", "content": f"请将以下文本翻译成中文，保持专业性和学术性：\n{text}"}
        ]
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V2.5",
            messages=messages,
            temperature=0.2,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"翻译失败: {str(e)}")
        return text

def translate_structure(structure: Dict[str, str]) -> Dict[str, str]:
    """翻译论文结构的各个部分"""
    section_translations = {
        "abstract": "摘要",
        "introduction": "引言",
        "methodology": "研究方法",
        "results": "研究结果",
        "discussion": "讨论",
        "conclusion": "结论",
        "references": "参考文献"
    }
    
    translated_structure = {}
    for section, content in structure.items():
        # 翻译章节名称
        translated_section = section_translations.get(section.lower(), section)
        # 翻译内容
        if detect_language(content) == "en":
            translated_content = translate_to_chinese(content)
        else:
            translated_content = content
        translated_structure[translated_section] = translated_content
    
    return translated_structure

def get_node_color(title: str, level: int) -> dict:
    """根据节点标题和层级获取颜色"""
    title_lower = title.lower().replace(" ", "_")
    
    if level == 1:
        color_scheme = THEME_COLORS["level1"]
        background = color_scheme.get(title_lower, color_scheme["default"])
        return {"background": background, "color": "#FFFFFF"}
    elif level == 2:
        color_scheme = THEME_COLORS["level2"]
        background = color_scheme.get(title_lower, color_scheme["default"])
        return {"background": background, "color": "#333333"}
    elif level == 3:
        color_scheme = THEME_COLORS["level3"]
        background = color_scheme.get(title_lower, color_scheme["default"])
        return {"background": background, "color": "#666666"}
    else:
        return THEME_COLORS["content"]

def create_node(title: str, content: Any, level: int = 1) -> dict:
    """创建节点"""
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

def create_xmind_file(structure: Dict[str, Any], filename: str) -> str:
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
            chapter_node = create_node(chapter, content)
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
        output_path = Path("static/mindmaps") / f"{filename.replace('.pdf', '')}_structure.xmind"
        output_path.parent.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(temp_dir))
        
        # 清理临时文件
        shutil.rmtree(temp_dir)
        
        return str(output_path)
    except Exception as e:
        logger.error(f"创建XMind文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建XMind文件失败: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """返回主页"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    api_key: str = Form(...),
    model_name: str = Form(...)
):
    try:
        # 初始化 OpenAI 客户端
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.siliconflow.cn/v1"
        )
        
        # 读取文件内容
        contents = await file.read()
        
        # 提取文本
        text = extract_text_from_pdf(contents)
        if not text:
            raise HTTPException(status_code=400, detail="无法从PDF中提取文本")
        
        # 检测语言
        language = detect_language(text)
        
        # 提取关键词
        keywords = extract_keywords(text, language, client, model_name)
        
        # 分析论文结构
        structure = analyze_paper_structure(text, client, model_name)
        
        # 生成XMind文件
        xmind_path = create_xmind_file(structure, file.filename)
        
        return {
            "filename": file.filename,
            "language": language,
            "paper_length": len(text),
            "keywords": keywords,
            "structure": structure,
            "xmind_path": xmind_path
        }
    except Exception as e:
        logger.error(f"处理文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_xmind(filename: str):
    """下载XMind文件"""
    try:
        # 移除文件名中的.pdf后缀（如果存在）
        filename = filename.replace('.pdf', '')
        file_path = f"static/mindmaps/{filename}_structure.xmind"
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            path=file_path,
            filename=f"{filename}_structure.xmind",
            media_type="application/octet-stream"
        )
    except Exception as e:
        logger.error(f"下载文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("正在启动服务器...")
    try:
        logger.info("服务器将在 http://127.0.0.1:8080 启动")
        logger.info("请使用浏览器访问上述地址")
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}")
        logger.info("请检查端口8080是否被占用")
        logger.info("如果端口被占用，可以尝试使用其他端口") 