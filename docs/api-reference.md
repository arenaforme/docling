# Docling-Serve API 参考文档

> 服务地址：`http://47.92.54.66:5001`
> 最后更新：2026-01-15

## 概述

Docling-Serve 是一个文档转换服务，支持将 PDF、DOCX、HTML 等格式转换为 Markdown、JSON 等结构化格式。

**重要说明：** 本服务默认使用**百度云 OCR** 进行文字识别，无需客户端配置 API 密钥。

## 快速开始

### 最简单的调用示例

```bash
curl -X POST "http://47.92.54.66:5001/v1/convert/file" \
  -F "files=@your_document.pdf" \
  -F 'options={"do_ocr":true}'
```

### Python 示例

```python
import requests

url = "http://47.92.54.66:5001/v1/convert/file"
files = {"files": open("your_document.pdf", "rb")}
data = {"options": '{"do_ocr": true}'}

response = requests.post(url, files=files, data=data)
result = response.json()

# 获取 Markdown 内容
markdown_content = result["document"]["md_content"]
print(markdown_content)
```

---

## API 端点

### 1. 健康检查

检查服务是否正常运行。

```
GET /health
```

**响应示例：**
```json
{
  "status": "ok"
}
```

---

### 2. 同步转换文件

上传文件并等待转换完成，适合小文件（< 5MB）。

```
POST /v1/convert/file
```

**请求格式：** `multipart/form-data`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | File | 是 | 要转换的文件，支持多文件 |
| `options` | JSON String | 否 | 转换选项（见下方详细说明） |
| `target_type` | String | 否 | 输出类型：`inbody`（默认）或 `zip` |

**options 参数详细说明：**

```json
{
  "do_ocr": true,
  "ocr_engine": "baidu",
  "to_formats": ["md"],
  "from_formats": ["pdf", "docx", "html", "pptx", "xlsx", "image"],
  "force_ocr": false,
  "ocr_lang": null,
  "do_table_structure": true,
  "table_mode": "accurate",
  "include_images": true,
  "images_scale": 2.0,
  "page_range": [null, null],
  "document_timeout": 600
}
```

**options 字段说明：**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `do_ocr` | bool | `true` | 是否启用 OCR |
| `ocr_engine` | string | `"baidu"` | OCR 引擎（本服务默认百度） |
| `to_formats` | array | `["md"]` | 输出格式：`md`, `json`, `html`, `text`, `doctags` |
| `from_formats` | array | 全部 | 输入格式过滤 |
| `force_ocr` | bool | `false` | 强制使用 OCR 替换原有文字 |
| `ocr_lang` | array | `null` | OCR 语言列表 |
| `do_table_structure` | bool | `true` | 是否识别表格结构 |
| `table_mode` | string | `"accurate"` | 表格模式：`fast` 或 `accurate` |
| `include_images` | bool | `true` | 是否提取图片 |
| `images_scale` | float | `2.0` | 图片缩放比例 |
| `page_range` | array | `[null, null]` | 页码范围，如 `[1, 10]` |
| `document_timeout` | float | `600` | 单文档超时时间（秒） |

**响应示例：**

```json
{
  "document": {
    "md_content": "# 文档标题\n\n这是文档内容...",
    "json_content": null,
    "html_content": null,
    "text_content": null,
    "doctags_content": null
  },
  "status": "success",
  "errors": [],
  "processing_time": 12.5,
  "timings": {}
}
```

**curl 示例：**

```bash
# 基本调用（使用默认百度 OCR）
curl -X POST "http://47.92.54.66:5001/v1/convert/file" \
  -H "accept: application/json" \
  -F "files=@document.pdf" \
  -F 'options={"do_ocr":true}'

# 指定输出格式为 JSON
curl -X POST "http://47.92.54.66:5001/v1/convert/file" \
  -F "files=@document.pdf" \
  -F 'options={"do_ocr":true,"to_formats":["json"]}'

# 只转换前 5 页
curl -X POST "http://47.92.54.66:5001/v1/convert/file" \
  -F "files=@document.pdf" \
  -F 'options={"do_ocr":true,"page_range":[1,5]}'
```

---

### 3. 异步转换文件

上传文件并立即返回任务 ID，适合大文件。

```
POST /v1/convert/file/async
```

**请求格式：** 与同步接口相同

**响应示例：**

```json
{
  "task_id": "abc123-def456-ghi789",
  "task_type": "convert",
  "task_status": "pending",
  "task_position": 0,
  "task_meta": null
}
```

**任务状态值：**

| 状态 | 说明 |
|------|------|
| `pending` | 等待处理 |
| `started` | 正在处理 |
| `success` | 处理成功 |
| `failure` | 处理失败 |

---

### 4. 查询任务状态

```
GET /v1/status/poll/{task_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wait` | float | `0.0` | 等待完成的秒数（长轮询） |

**响应示例：**

```json
{
  "task_id": "abc123-def456-ghi789",
  "task_type": "convert",
  "task_status": "success",
  "task_position": null,
  "task_meta": {
    "progress": 1.0,
    "pages_processed": 24,
    "pages_total": 24
  }
}
```

---

### 5. 获取任务结果

```
GET /v1/result/{task_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 任务 ID |

**响应格式：** 与同步转换接口相同

---

### 6. 从 URL 转换文档

```
POST /v1/convert/source
```

**请求格式：** `application/json`

**请求体示例：**

```json
{
  "sources": [
    {
      "kind": "http",
      "url": "https://example.com/document.pdf"
    }
  ],
  "options": {
    "do_ocr": true,
    "to_formats": ["md"]
  }
}
```

---

## 完整代码示例

### Python - 同步转换

```python
import requests
import json

def convert_document(file_path: str, server_url: str = "http://47.92.54.66:5001"):
    """同步转换文档"""
    url = f"{server_url}/v1/convert/file"

    with open(file_path, "rb") as f:
        files = {"files": (file_path, f)}
        data = {
            "options": json.dumps({
                "do_ocr": True,
                "to_formats": ["md"]
            })
        }
        response = requests.post(url, files=files, data=data)

    if response.status_code == 200:
        result = response.json()
        return result["document"]["md_content"]
    else:
        raise Exception(f"转换失败: {response.text}")

# 使用示例
markdown = convert_document("test.pdf")
print(markdown)
```

### Python - 异步转换（大文件）

```python
import requests
import json
import time

def convert_document_async(file_path: str, server_url: str = "http://47.92.54.66:5001"):
    """异步转换文档（适合大文件）"""

    # 1. 提交任务
    url = f"{server_url}/v1/convert/file/async"
    with open(file_path, "rb") as f:
        files = {"files": (file_path, f)}
        data = {
            "options": json.dumps({
                "do_ocr": True,
                "to_formats": ["md"]
            })
        }
        response = requests.post(url, files=files, data=data)

    if response.status_code != 200:
        raise Exception(f"提交任务失败: {response.text}")

    task_id = response.json()["task_id"]
    print(f"任务已提交，ID: {task_id}")

    # 2. 轮询状态
    status_url = f"{server_url}/v1/status/poll/{task_id}"
    while True:
        response = requests.get(status_url)
        status = response.json()
        task_status = status["task_status"]

        if task_status == "success":
            print("任务完成！")
            break
        elif task_status == "failure":
            raise Exception("任务失败")
        else:
            meta = status.get("task_meta") or {}
            progress = meta.get("progress", 0)
            print(f"处理中... {progress*100:.1f}%")
            time.sleep(5)

    # 3. 获取结果
    result_url = f"{server_url}/v1/result/{task_id}"
    response = requests.get(result_url)
    result = response.json()

    return result["document"]["md_content"]

# 使用示例
markdown = convert_document_async("large_document.pdf")
print(f"转换完成，内容长度: {len(markdown)} 字符")
```

### JavaScript/Node.js 示例

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function convertDocument(filePath) {
    const serverUrl = 'http://47.92.54.66:5001';

    const form = new FormData();
    form.append('files', fs.createReadStream(filePath));
    form.append('options', JSON.stringify({
        do_ocr: true,
        to_formats: ['md']
    }));

    const response = await axios.post(
        `${serverUrl}/v1/convert/file`,
        form,
        { headers: form.getHeaders() }
    );

    return response.data.document.md_content;
}

// 使用示例
convertDocument('test.pdf')
    .then(markdown => console.log(markdown))
    .catch(err => console.error(err));
```

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 任务不存在 |
| 504 | 处理超时 |
| 500 | 服务器内部错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

---

## 支持的文件格式

### 输入格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| PDF | `.pdf` | 支持扫描件和电子版 |
| Word | `.docx` | Microsoft Word 文档 |
| PowerPoint | `.pptx` | Microsoft PowerPoint |
| Excel | `.xlsx` | Microsoft Excel |
| HTML | `.html`, `.htm` | 网页文件 |
| Markdown | `.md` | Markdown 文件 |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | 图片文件 |

### 输出格式

| 格式 | 值 | 说明 |
|------|-----|------|
| Markdown | `md` | 默认输出格式 |
| JSON | `json` | 结构化 JSON |
| HTML | `html` | HTML 格式 |
| 纯文本 | `text` | 纯文本格式 |
| DocTags | `doctags` | Docling 内部格式 |

---

## 性能建议

1. **小文件（< 5MB）**：使用同步接口 `/v1/convert/file`
2. **大文件（> 5MB）**：使用异步接口 `/v1/convert/file/async`
3. **批量处理**：建议串行提交，避免并发过高
4. **超时设置**：大文件建议设置较长的 `document_timeout`

---

## 在线文档

访问 Swagger UI 查看完整 API 文档：

- Swagger UI: `http://47.92.54.66:5001/swagger`
- ReDoc: `http://47.92.54.66:5001/docs`
- Scalar: `http://47.92.54.66:5001/scalar`
