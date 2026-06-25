# Third-party vendored code

## MinerU (`mineru/`)

PDF 解析能力来自 [MinerU](https://github.com/opendatalab/MinerU)（Apache License 2.0 + 附加条款）。

- 源码位置：`src/third_party/mineru/`
- 许可全文：`src/third_party/mineru/LICENSE.md`
- 项目级说明：`NOTICE`（仓库根目录）

ChronoPaper 通过 `src/third_party/mineru_bootstrap.py` 加载该包。

运行依赖（按需安装）：

```bash
# CPU / pipeline
pip install torch torchvision transformers onnxruntime pypdfium2 opencv-python-headless ...

# 或参考 requirements.txt 中 MinerU 相关注释
```
