# 发布检查单（Release Checklist）

> 最后更新：2026-09-15（P2-6 整改：把合规承诺固化为可勾选门禁）。
> 适用：便携包 / 桌面壳 / 任何对外分发的形态。逐项通过后 tag/release。

## 1. GPL-3.0（comfy_kernel / comfy-aimdo）——分发即触发

- [ ] 包内随附 GPL-3.0 许可全文（`docs/GPL_COMPLIANCE.md` §2 清单）；
- [ ] comfy_kernel 对应源码可获取：GitHub 上游链接 + vendored commit pin（`9883be7c`）随包说明；
- [ ] 保留上游版权声明（Comfy-Org 等）；
- [ ] `docs/GPL_COMPLIANCE.md` §2 分发前自查清单全部勾选。

## 2. 模型权重隔离（USER_AGREEMENT §6 前提）

- [ ] `scripts/package_app.py` 的 `_assert_no_weights_in` 断言通过（打包自动执行）；
- [ ] 包内无 `*.safetensors / *.ckpt / *.pt / *.pth / *.gguf / *.onnx`；
- [ ] README/发布说明保留"分发包默认不含任何模型权重"表述。

## 3. AI 生成内容标识

- [ ] 输出文件名 `_AI` 后缀默认开启（`config.output.explicit_ai_label`）；
- [ ] DCT 隐式水印开启且失败侧车策略生效（`config.watermark`）；
- [ ] 首启协议确认弹窗可用（`image_mm:agreement:v1`）。

## 4. 法务文件四件套随包

- [ ] LICENSE / NOTICE / USER_AGREEMENT.md / PRIVACY_POLICY.md / THIRD_PARTY_NOTICES.md 在包内（package_app ROOT_EXTRA 自动带上）。

## 5. 待办（人工/后续版本）

- [ ] 人物 LoRA 生成时的一次性合规提示（UI 层，依赖前端改动）；
- [ ] 依赖许可报告插件（Licensee / gradle license-report 等价物）评估。

*本检查单为发布自查工具，不构成法律意见。*
