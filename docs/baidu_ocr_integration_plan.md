# 百度云 OCR 集成实施计划

> 文档创建日期：2026-01-14
> 状态：待实施

## 1. 背景

为 Docling 项目集成百度云 OCR 服务，扩展 OCR 能力，支持通过百度 API 进行文字识别。

### 1.1 核心动机：解决内存占用问题

**问题**：当前 docling-serve 使用本地 OCR 模型（如 EasyOCR、RapidOCR）时，内存占用过高，限制了服务的部署灵活性。

**解决方案**：引入百度云 OCR，将 OCR 计算卸载到云端，显著降低本地内存占用。

## 2. 架构分析

### 2.1 Docling OCR 系统架构

Docling 采用**插件式工厂模式**管理 OCR 引擎：

```
OcrOptions (配置类) → OcrFactory → BaseOcrModel (实现类)
```

### 2.2 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `BaseOcrModel` | `docling/models/base_ocr_model.py` | OCR 模型基类，定义接口 |
| `OcrOptions` | `docling/datamodel/pipeline_options.py` | OCR 配置基类 |
| `OcrFactory` | `docling/models/factories/ocr_factory.py` | OCR 引擎工厂 |
| `defaults.py` | `docling/models/plugins/defaults.py` | 插件注册入口 |

### 2.3 现有 OCR 引擎

- `EasyOcrModel` - EasyOCR 引擎
- `RapidOcrModel` - RapidOCR 引擎
- `TesseractOcrModel` - Tesseract 引擎
- `OcrMacModel` - macOS 原生 OCR
- `OcrAutoModel` - 自动选择引擎

## 3. 设计决策

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 认证方式 | 配置文件 | 支持 JSON 配置文件读取 API Key |
| API 类型 | 多种可配置 | 支持标准版和高精度版切换 |
| 位置信息 | 仅文字内容 | 使用 `_basic` 版本 API，更省配额 |

## 4. 文件变更清单

| 序号 | 文件路径 | 操作 | 说明 |
|------|----------|------|------|
| 1 | `docling/datamodel/pipeline_options.py` | 修改 | 新增 `BaiduOcrOptions` 配置类 |
| 2 | `docling/models/stages/ocr/baidu_ocr_model.py` | 新建 | 百度 OCR 模型实现 |
| 3 | `docling/models/plugins/defaults.py` | 修改 | 注册 `BaiduOcrModel` |
| 4 | `pyproject.toml` | 修改 | 添加 `baidu` 可选依赖组 |
| 5 | `tests/test_backend_baidu_ocr.py` | 新建 | 单元测试 |

## 5. 详细设计

### 5.1 BaiduOcrOptions 配置类

```python
from enum import Enum
from typing import ClassVar, List, Literal, Optional
from pydantic import ConfigDict

class BaiduOcrApiType(str, Enum):
    """百度 OCR API 类型"""
    GENERAL_BASIC = "general_basic"      # 通用文字识别（标准版）
    ACCURATE_BASIC = "accurate_basic"    # 通用文字识别（高精度版）

class BaiduOcrOptions(OcrOptions):
    """Options for Baidu Cloud OCR engine."""

    kind: ClassVar[Literal["baidu"]] = "baidu"
    lang: List[str] = ["CHN_ENG"]

    # 认证配置 - 支持从配置文件读取
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    config_file: Optional[str] = None   # JSON 配置文件路径

    # API 配置
    api_type: BaiduOcrApiType = BaiduOcrApiType.GENERAL_BASIC
    timeout: float = 10.0

    # OCR 参数
    detect_direction: bool = False
    confidence_threshold: float = 0.5

    model_config = ConfigDict(extra="forbid")
```

### 5.2 配置文件格式

JSON 配置文件 `baidu_ocr_config.json`：

```json
{
  "api_key": "your_api_key_here",
  "secret_key": "your_secret_key_here"
}
```

### 5.3 BaiduOcrModel 核心逻辑

```python
class BaiduOcrModel(BaseOcrModel):
    """Baidu Cloud OCR Model implementation."""

    def __init__(self, enabled, artifacts_path, options, accelerator_options):
        super().__init__(...)
        self._access_token = None
        self._token_expires_at = None
        self._load_credentials()

    def _load_credentials(self):
        """从配置文件或参数加载认证信息"""
        if self.options.config_file:
            config = json.load(open(self.options.config_file))
            self.api_key = config.get("api_key")
            self.secret_key = config.get("secret_key")

    def _get_access_token(self) -> str:
        """获取百度 OAuth Access Token（带缓存）"""
        # Token 有效期 30 天，需要缓存

    def _call_ocr_api(self, image: Image) -> List[dict]:
        """调用百度 OCR API"""
        # 1. 图片转 Base64
        # 2. 构建请求
        # 3. 解析响应

    def __call__(self, conv_res, page_batch) -> Iterable[Page]:
        """处理页面批次"""
        # 遍历页面，对 OCR 区域调用 API
```

### 5.4 百度 OCR API 端点

| API 类型 | 端点 | 说明 |
|----------|------|------|
| 标准版 | `https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic` | 免费额度多 |
| 高精度版 | `https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic` | 精度更高 |

## 6. 使用示例

### 6.1 基本用法

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import BaiduOcrOptions, PdfPipelineOptions

# 方式1：使用配置文件
ocr_options = BaiduOcrOptions(config_file="~/.baidu_ocr.json")

# 方式2：直接传参
ocr_options = BaiduOcrOptions(
    api_key="your_api_key",
    secret_key="your_secret_key"
)

# 配置 Pipeline
pipeline_options = PdfPipelineOptions(ocr_options=ocr_options)

# 创建转换器
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
    }
)

# 转换文档
result = converter.convert("document.pdf")
print(result.document.export_to_markdown())
```

### 6.2 使用高精度版 API

```python
from docling.datamodel.pipeline_options import BaiduOcrOptions, BaiduOcrApiType

ocr_options = BaiduOcrOptions(
    config_file="~/.baidu_ocr.json",
    api_type=BaiduOcrApiType.ACCURATE_BASIC
)
```

## 7. 实施顺序

| 步骤 | 任务 | 预计工作量 |
|------|------|------------|
| Step 1 | 在 `pipeline_options.py` 添加 `BaiduOcrApiType` 和 `BaiduOcrOptions` | 小 |
| Step 2 | 创建 `baidu_ocr_model.py` 实现核心逻辑 | 中 |
| Step 3 | 在 `defaults.py` 注册新引擎 | 小 |
| Step 4 | 更新 `pyproject.toml` 添加可选依赖 | 小 |
| Step 5 | 编写单元测试 | 中 |

## 8. 注意事项

### 8.1 错误处理

需要处理以下异常情况：
- 网络超时
- API 配额限制（QPS / 日调用量）
- 认证失败（Token 过期）
- 图片格式不支持

### 8.2 性能考虑

- Access Token 缓存（有效期 30 天）
- 批量请求优化（如支持）
- 超时重试机制

### 8.3 安全性

- API Key 不应硬编码在代码中
- 配置文件应设置适当权限（如 `chmod 600`）
- 日志中不应打印敏感信息

## 9. 内存优化分析

### 9.1 问题背景

docling-serve 部署时，本地 OCR 模型的内存消耗主要来自：

- **模型权重**：检测模型 + 识别模型（100-500 MB）
- **推理框架**：PyTorch / ONNX Runtime（500 MB+）
- **运行时开销**：模型推理的中间张量、图像缓冲区

### 9.2 内存占用对比

| 对比项 | 本地 OCR (EasyOCR) | 百度云 OCR |
|--------|-------------------|------------|
| 模型加载 | 需加载到内存 (100-500 MB) | 无需加载 |
| 推理框架 | PyTorch/ONNX (500 MB+) | 无 |
| 运行时内存 | **1-2 GB+** | **几十 MB** |
| 依赖项大小 | 重型 ML 依赖 | 仅 `requests` |

**预估内存节省：90%+**

### 9.3 权衡因素

| 因素 | 本地 OCR | 百度云 OCR |
|------|----------|------------|
| 内存占用 | ❌ 高 | ✅ 极低 |
| 响应延迟 | ✅ 低 (本地计算) | ⚠️ 较高 (网络往返 200-500ms) |
| 运行成本 | ✅ 无额外费用 | ⚠️ API 调用费用 |
| 离线能力 | ✅ 支持 | ❌ 需要网络 |
| 数据隐私 | ✅ 数据不出本地 | ⚠️ 数据上传到百度 |
| 并发能力 | ✅ 取决于硬件 | ⚠️ 受 QPS 配额限制 |

### 9.4 适用场景建议

**推荐使用百度云 OCR：**
- ✅ 服务器内存资源有限
- ✅ 文档处理量在 API 配额范围内
- ✅ 对延迟要求不苛刻（非实时场景）
- ✅ 数据不涉及高度敏感信息

**建议保留本地 OCR：**
- 离线 / 内网 / air-gapped 环境
- 高度敏感数据（金融、医疗、政务）
- 超高并发需求（超出 API QPS 限制）
- 对延迟极度敏感的实时场景

## 10. 参考资料

- [百度 OCR API 文档](https://cloud.baidu.com/doc/OCR/index.html)
- [百度 OAuth 认证](https://ai.baidu.com/ai-doc/REFERENCE/Ck3dwjhhu)
- [Docling 官方文档](https://docling-project.github.io/docling/)

## 11. 未来扩展：docling-serve 集成

### 11.1 服务化场景需求

在 docling-serve 中使用百度 OCR 时，需要考虑以下场景：

| 场景 | 需求 | 当前设计支持 |
|------|------|--------------|
| 容器化部署 | 环境变量配置 | ⚠️ 需扩展 |
| 多租户 | 不同用户使用不同 API Key | ⚠️ 需扩展 |
| 高并发 | Token 缓存线程安全 | ✅ 已考虑 |
| 服务监控 | 结构化错误返回 | ⚠️ 需扩展 |

### 11.2 当前设计的服务化兼容性

为便于未来 docling-serve 集成，当前实现需预留以下扩展点：

**配置层面：**
```python
class BaiduOcrOptions(OcrOptions):
    # 支持环境变量回退
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("BAIDU_OCR_API_KEY"))
    secret_key: Optional[str] = Field(default_factory=lambda: os.getenv("BAIDU_OCR_SECRET_KEY"))
```

**缓存层面：**
```python
# Access Token 缓存需要线程安全
import threading

class BaiduOcrModel(BaseOcrModel):
    _token_lock = threading.Lock()
    _access_token: Optional[str] = None
    _token_expires_at: Optional[float] = None
```

### 11.3 docling-serve 集成待办事项

未来集成 docling-serve 时需要完成：

- [ ] 支持通过环境变量配置认证信息（`BAIDU_OCR_API_KEY`、`BAIDU_OCR_SECRET_KEY`）
- [ ] 支持请求级别的 API Key 覆盖（多租户场景）
- [ ] 添加请求限流机制（遵守百度 QPS 限制）
- [ ] 结构化错误响应（便于 REST API 返回）
- [ ] 添加 OCR 调用指标（调用次数、延迟、错误率）
- [ ] 健康检查支持（验证 API Key 有效性）

### 11.4 服务化部署配置示例

**Docker 环境变量方式：**
```yaml
# docker-compose.yml
services:
  docling-serve:
    image: docling-serve:latest
    environment:
      - BAIDU_OCR_API_KEY=${BAIDU_OCR_API_KEY}
      - BAIDU_OCR_SECRET_KEY=${BAIDU_OCR_SECRET_KEY}
      - BAIDU_OCR_API_TYPE=general_basic
```

**Kubernetes ConfigMap/Secret：**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: baidu-ocr-credentials
type: Opaque
stringData:
  api-key: "your_api_key"
  secret-key: "your_secret_key"
```
