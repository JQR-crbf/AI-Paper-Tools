# 智能计算机论文分析工具

这是一个基于Python的智能论文分析工具，可以帮助用户快速分析计算机领域的学术论文，并生成结构化的思维导图。

## 功能特点

- **PDF论文解析**：支持解析PDF格式的学术论文
- **多语言支持**：自动识别中英文论文
- **智能关键词提取**：
  - 中文论文：使用jieba分词提取关键词
  - 英文论文：使用DeepSeek API提取专业术语
- **论文结构分析**：
  - 自动识别论文章节结构
  - 提取各章节主要内容
  - 支持多级章节分析
- **思维导图生成**：
  - 自动生成XMind格式的思维导图
  - 多级结构清晰展示
  - 使用不同颜色区分层级
  - 支持导出和下载

## 技术特点

- 使用FastAPI构建后端服务
- 使用tkinter构建GUI界面
- 集成DeepSeek API进行智能分析
- 支持多种PDF解析方式（PyPDF2/pdfplumber）
- 使用jieba进行中文分词
- 支持XMind文件格式生成

## 安装说明

1. 克隆项目到本地：
```bash
git clone https://github.com/你的用户名/paper-analyzer.git
cd paper-analyzer
```

2. 创建并激活虚拟环境（可选）：
```bash
python -m venv paper_analysis
.\paper_analysis\Scripts\activate
```

3. 安装依赖包：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行GUI程序：
```bash
python gui.py
```

2. 在GUI界面中：
   - 输入DeepSeek API密钥
   - 选择模型版本（DeepSeek-V3/V2.5/V2/V1）
   - 选择要分析的PDF论文
   - 点击"分析论文"按钮
   - 等待分析完成
   - 点击"下载思维导图"保存结果

## 配置说明

- 程序会自动保存API设置到本地配置文件
- 生成的思维导图保存在`static/mindmaps`目录下
- 支持自定义思维导图颜色主题

## 注意事项

- 需要有效的DeepSeek API密钥
- PDF文件需要包含可提取的文本内容
- 建议使用标准格式的学术论文
- 思维导图文件使用XMind格式，需要XMind软件打开

## 依赖包列表

- fastapi==0.103.1
- uvicorn==0.23.2
- python-multipart==0.0.6
- PyPDF2==3.0.1
- pdfplumber==0.10.3
- jieba==0.42.1
- openai==1.12.0
- aiofiles==23.2.1
- python-dotenv==1.0.0
- python-jose==3.3.0
- passlib==1.7.4
- jinja2==3.1.2

## 项目结构

```
paper-analyzer/
├── gui.py              # GUI主程序
├── main.py             # 后端服务程序
├── requirements.txt    # 依赖包列表
├── README.md          # 项目说明文档
├── .gitignore         # Git忽略文件
├── static/            # 静态文件目录
│   └── mindmaps/      # 思维导图存储目录
├── templates/         # 模板文件目录
└── dict/             # 字典文件目录
```

## 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。

## 许可证

MIT License 