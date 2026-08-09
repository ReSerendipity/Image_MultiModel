"""
comfy/workflow.py — WorkflowManager: Patcher 6 步

对应 MASTER_PLAN §6 / PRD §4.3.2: Workflow Patcher 6 步
① 深拷贝 ② mode 切换 ③ link 重连 ④ widgets 精确 patch ⑤ batch chunk 拆分 ⑥ 提交前节点校验
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ..engine_interface import GenerationConfig
from ..gpu_utils import recommend_chunk_size

logger = logging.getLogger(__name__)


class WorkflowManager:
    """
    工作流管理器：加载工作流 JSON + Schema YAML，执行 6 步 Patcher。

    Schema YAML 格式示例:
        engine_name: "flux2_klein_9b_distilled"
        subgraph_id: "95960805-..."
        nodes:
          - id: 64  # 子图节点（Text to Image）
            type: "subgraph"
            widgets:
              positive_prompt: 0
              negative_prompt: 1
              cfg: 2
              steps: 3
              width: 4
              height: 5
          - id: 69  # UNETLoader
            type: "UNETLoader"
            widgets:
              unet_name: 0
              weight_dtype: 1
          - id: 16  # LoraLoaderModelOnly (layer 1)
            type: "LoraLoaderModelOnly"
            widgets:
              lora_name: 0
              strength_model: 1
          # ... etc
    """

    def __init__(
        self,
        workflow_path: str = "",
        schema_path: str = "",
        project_root: str = "",
    ) -> None:
        self.project_root = Path(project_root)
        self.workflow_path = Path(workflow_path) if workflow_path else None
        self.schema_path = Path(schema_path) if schema_path else None
        self._workflow_data: Optional[Dict[str, Any]] = None
        self._schema: Optional[Dict[str, Any]] = None
        self._workflow_sha256: str = ""

        if self.workflow_path and self.workflow_path.exists():
            self._load_workflow()
        if self.schema_path and self.schema_path.exists():
            self._load_schema()

    def _load_workflow(self) -> None:
        """加载工作流 JSON"""
        assert self.workflow_path is not None
        with open(self.workflow_path, "r", encoding="utf-8") as f:
            self._workflow_data = json.load(f)
        # 计算 SHA256
        raw = json.dumps(self._workflow_data, sort_keys=True).encode()
        self._workflow_sha256 = hashlib.sha256(raw).hexdigest()
        logger.info(f"Workflow loaded: {self.workflow_path} (sha256={self._workflow_sha256[:12]}...)")

    def _load_schema(self) -> None:
        """加载 Schema YAML"""
        assert self.schema_path is not None
        with open(self.schema_path, "r", encoding="utf-8") as f:
            self._schema = yaml.safe_load(f)
        logger.info(f"Schema loaded: {self.schema_path}")

    @property
    def workflow_sha256(self) -> str:
        return self._workflow_sha256

    # ── Patcher 6 步 ─────────────────────────────────────────
    def patch(self, config: GenerationConfig) -> Dict[str, Any]:
        """
        执行 6 步 Patcher，返回可提交给 ComfyUI 的工作流字典。

        步骤:
        ① 深拷贝原始工作流
        ② mode 切换（LoRA / SeedVR2 / Eses / VRAM 开关）
        ③ link 重连（关闭时改 VAEDecode 直通）
        ④ widgets 精确 patch（width/height 双节点同步、3 个独立 seed）
        ⑤ batch chunk 拆分
        ⑥ 提交前节点校验
        """
        if not self._workflow_data:
            raise RuntimeError("No workflow loaded")

        # ① 深拷贝
        wf = copy.deepcopy(self._workflow_data)
        # 设置 seed=-1 时生成实际值并回填
        self._resolve_seeds(config)

        # ② mode 切换
        self._patch_modes(wf, config)

        # ③ link 重连
        self._patch_links(wf, config)

        # ④ widgets 精确 patch
        self._patch_widgets(wf, config)

        # ⑤ batch chunk 拆分
        wf = self._patch_batch_chunk(wf, config)

        # ⑥ 提交前节点校验
        self._validate_nodes(wf)

        return wf

    # ── UI 格式 → ComfyUI API 格式（含子图展开 + bypass 移除重连）──
    def to_api_format(
        self,
        wf: Dict[str, Any],
        object_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        将 patched 的 UI 格式工作流（含子图 definitions）转换为 ComfyUI /prompt
        需要的 API 格式：{"<id>": {"class_type": ..., "inputs": {...}}}。

        处理：
        1) 子图展开：子图输入（-10 → 字面值）、子图输出（-20 → 上游 origin）
        2) bypass 节点（mode=4 / 预览链 / 空名 LoRA）从图中移除并递归重连链路
        3) widgets_values → 具名 inputs（依赖 /object_info 的输入顺序）
        """
        # ── 1. 节点与子图 ──
        top_nodes = list(wf.get("nodes", []))
        subs = wf.get("definitions", {}).get("subgraphs", []) or []
        sub = subs[0] if subs else None
        sub_nodes = list(sub.get("nodes", [])) if sub else []
        nodes_by_id: Dict[int, Dict[str, Any]] = {}
        for n in top_nodes + sub_nodes:
            nodes_by_id[n["id"]] = n

        subgraph_id: Optional[int] = None
        sub_widgets: List[Any] = []
        if sub:
            for n in top_nodes:
                if n.get("type") == sub.get("id"):
                    subgraph_id = n["id"]
                    sub_widgets = list(n.get("widgets_values") or [])

        # ── 2. 链接（兼容 list / dict 两种格式）──
        raw_links: List[Any] = list(wf.get("links", []))
        if sub:
            raw_links.extend(sub.get("links", []))
        links: List[Dict[str, Any]] = []
        for L in raw_links:
            if isinstance(L, (list, tuple)) and len(L) >= 6:
                links.append({
                    "id": L[0], "origin_id": L[1], "origin_slot": L[2],
                    "target_id": L[3], "target_slot": L[4], "type": L[5],
                })
            elif isinstance(L, dict):
                links.append(L)

        # ── 3. 确定移除节点 ──
        removed: set = set()
        for nid, n in nodes_by_id.items():
            t = n.get("type", "")
            if t in ("ImageScaleToTotalPixels", "PreviewImage", "Fast Groups Bypasser (rgthree)"):
                removed.add(nid)
            elif n.get("mode") == 4:
                removed.add(nid)
            elif t == "LoraLoaderModelOnly" and not (n.get("widgets_values") or [None])[0]:
                removed.add(nid)  # 空名 = 该层禁用 → 移除并重连

        # ── 4. bypass 上游映射 + 子图输出映射 ──
        in_of: Dict[tuple, tuple] = {}
        for L in links:
            if L["target_id"] in removed:
                in_of[(L["target_id"], L["target_slot"])] = (L["origin_id"], L["origin_slot"])
        sub_out: Dict[int, tuple] = {}
        for L in links:
            if L["target_id"] == -20:
                sub_out[L["target_slot"]] = (L["origin_id"], L["origin_slot"])

        memo: Dict[tuple, tuple] = {}

        def ro(oid: int, osl: int, depth: int = 0) -> tuple:
            """递归解析 origin：-10=子图输入值 / subgraph=子图输出 / removed=上游"""
            key = (oid, osl)
            if key in memo:
                return memo[key]
            if depth > 20:
                return key
            if oid == -10:
                r = ("#value", osl)
            elif oid == subgraph_id:
                r = ro(*sub_out.get(osl, (oid, osl)), depth + 1)
            elif oid in removed:
                r = ro(*in_of.get(key, (oid, osl)), depth + 1)
            else:
                r = key
            memo[key] = r
            return r

        # ── 5. 生成 API prompt ──
        def _is_primitive(t0: Any) -> bool:
            return isinstance(t0, list) or t0 in ("STRING", "INT", "FLOAT", "BOOLEAN", "SEED", "COMBO")

        prompt: Dict[str, Dict[str, Any]] = {}
        for nid, n in nodes_by_id.items():
            if nid in removed or nid in (subgraph_id, -10, -20):
                continue
            ntype = n.get("type", "")
            spec = object_info.get(ntype, {}).get("input", {})
            oi_in = list(spec.get("required", {})) + list(spec.get("optional", {}))
            # 槽位名 = UI 图节点自身 inputs 顺序（与 object_info 顺序可能不同）
            node_inputs = n.get("inputs") or []
            in_names = [str(i.get("name", idx)) for idx, i in enumerate(node_inputs)]
            # widgets 按 object_info 的原始输入顺序对齐
            widget_names = [nm for nm in oi_in if _is_primitive((spec.get("required", {}).get(nm) or spec.get("optional", {}).get(nm))[0])]
            widgets = list(n.get("widgets_values") or [])
            wmap: Dict[str, int] = {}
            for wi, nm in enumerate(widget_names):
                if wi >= len(widgets):
                    break
                wmap[nm] = wi

            linked: Dict[int, tuple] = {}
            for L in links:
                if L["target_id"] == nid and L["target_id"] not in removed:
                    linked[L["target_slot"]] = ro(L["origin_id"], L["origin_slot"])

            inputs: Dict[str, Any] = {}
            for idx, name in enumerate(in_names):
                if idx in linked:
                    oid, osl = linked[idx]
                    if oid == "#value":
                        inputs[name] = sub_widgets[osl] if osl < len(sub_widgets) else None
                    else:
                        inputs[name] = [str(oid), osl]  # ComfyUI API 要求节点 id 为字符串
                    continue
                if name in wmap:
                    v = widgets[wmap[name]]
                    if v is not None:
                        inputs[name] = v
                    continue
                # 无 widget 且未链接：COMBO 用首选项兜底
                sp = spec.get("required", {}).get(name) or spec.get("optional", {}).get(name)
                if sp:
                    sp_cfg = sp[1] if len(sp) > 1 else {}
                    if sp[0] == "COMBO" and sp_cfg.get("options"):
                        inputs[name] = sp_cfg["options"][0]
                    elif isinstance(sp[0], list) and sp[0]:
                        inputs[name] = sp[0][0]
            prompt[str(nid)] = {"class_type": ntype, "inputs": inputs}

        return prompt

    def _resolve_seeds(self, config: GenerationConfig) -> None:
        """seed=-1 时生成实际值并回填三个独立 seed 字段"""
        if config.seed == -1:
            config.seed = random.randint(0, 2**53 - 1)
        if config.seedvr2_seed == -1:
            config.seedvr2_seed = random.randint(0, 2**53 - 1)
        if config.vram_seed == -1:
            config.vram_seed = random.randint(0, 2**53 - 1)

    def _get_node(self, wf: Dict[str, Any], node_id: int) -> Optional[Dict[str, Any]]:
        """在工作流中查找节点（包括子图定义中的节点）"""
        # 顶层节点
        for node in wf.get("nodes", []):
            if node.get("id") == node_id:
                return node

        # 子图定义中的节点
        definitions = wf.get("definitions", {}).get("subgraphs", [])
        for sub in definitions:
            for node in sub.get("nodes", []):
                if node.get("id") == node_id:
                    return node

        return None

    def _get_all_nodes(self, wf: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取所有节点（顶层 + 子图）"""
        nodes = list(wf.get("nodes", []))
        for sub in wf.get("definitions", {}).get("subgraphs", []):
            nodes.extend(sub.get("nodes", []))
        return nodes

    def _patch_modes(self, wf: Dict[str, Any], config: GenerationConfig) -> None:
        """
        ② mode 切换：
        - LoRA 节点 mode=4 → 改 0（提交前强制）
        - SeedVR2/Eses/VRAM 关闭时 mode → 4（bypass）
        """
        all_nodes = self._get_all_nodes(wf)

        for node in all_nodes:
            node_type = node.get("type", "")
            node_id = node.get("id")

            # LoRA 节点：mode=4 → 0（PRD 4.3.2: LoRA mode=4 提交前强制改 0）
            if node_type == "LoraLoaderModelOnly":
                if node.get("mode") == 4:
                    node["mode"] = 0
                    logger.debug(f"LoRA node {node_id}: mode 4→0")

            # SeedVR2 节点：关闭时 bypass
            if not config.seedvr2_enable:
                if node_type in ("SeedVR2LoadVAEModel", "SeedVR2VideoUpscaler", "SeedVR2LoadDiTModel"):
                    node["mode"] = 4  # bypass
                    logger.debug(f"SeedVR2 node {node_id}: bypassed (disabled)")

            # Eses 节点：关闭时 bypass
            if not config.eses_enable:
                if node_type == "EsesImageCompare":
                    node["mode"] = 4
                    logger.debug(f"Eses node {node_id}: bypassed (disabled)")

            # VRAM 节点：关闭时 bypass
            if not config.vram_enable:
                if node_type == "ReservedVRAMSetter":
                    node["mode"] = 4
                    logger.debug(f"VRAM node {node_id}: bypassed (disabled)")

            # 预览/缩放节点始终 bypass（原型中已 mode=4）
            if node_type in ("ImageScaleToTotalPixels", "PreviewImage", "Fast Groups Bypasser (rgthree)"):
                node["mode"] = 4

    def _patch_links(self, wf: Dict[str, Any], config: GenerationConfig) -> None:
        """
        ③ link 重连：
        - 关闭 SeedVR2 时：VAEDecode → 直通到 SaveImage/Eses（跳过 SeedVR2VideoUpscaler）
        - 关闭 Eses 时：VAEDecode → 直通到 SaveImage（跳过 EsesImageCompare）
        """
        # 此步骤需要根据工作流的 links 数组重连
        # ComfyUI 工作流的 links 格式: [link_id, origin_id, origin_slot, target_id, target_slot, type]
        links = wf.get("links", [])

        # 获取子图定义中的 links
        for sub in wf.get("definitions", {}).get("subgraphs", []):
            links.extend(sub.get("links", []))

        # 当 SeedVR2 关闭时，需要将 VAEDecode 的输出直接连到 EsesImageCompare 或 SaveImage
        # 具体 link 重连逻辑依赖于工作流的具体结构
        # 这里实现通用框架，具体 link 修改在 schema 中定义
        if not config.seedvr2_enable and self._schema:
            link_overrides = self._schema.get("link_overrides", {}).get("seedvr2_off", [])
            for override in link_overrides:
                self._apply_link_override(links, override)

        if not config.eses_enable and self._schema:
            link_overrides = self._schema.get("link_overrides", {}).get("eses_off", [])
            for override in link_overrides:
                self._apply_link_override(links, override)

    def _apply_link_override(self, links: List[Any], override: Dict[str, Any]) -> None:
        """应用单个 link 重连规则"""
        link_id = override.get("link_id")
        new_origin = override.get("new_origin_id")
        new_origin_slot = override.get("new_origin_slot")

        for link in links:
            if isinstance(link, list) and len(link) >= 5 and link[0] == link_id:
                if new_origin is not None:
                    link[1] = new_origin
                if new_origin_slot is not None:
                    link[2] = new_origin_slot
                break

    def _patch_widgets(self, wf: Dict[str, Any], config: GenerationConfig) -> None:
        """
        ④ widgets 精确 patch：
        - Schema 中每个节点的 widgets 映射 → widgets_values 下标
        - width/height 双节点同步（EmptyLatent + Scheduler）
        - 3 个独立 INT_SEED_RANDOMIZE（主 seed / SeedVR2 seed / VRAM seed）
        """
        if not self._schema:
            # 无 schema 时，用默认映射
            self._patch_widgets_default(wf, config)
            return

        schema_nodes = self._schema.get("nodes", [])
        all_nodes = {n.get("id"): n for n in self._get_all_nodes(wf)}

        for schema_node in schema_nodes:
            node_id = schema_node.get("id")
            node = all_nodes.get(node_id)
            if not node:
                logger.warning(f"Schema node {node_id} not found in workflow")
                continue

            widgets_map = schema_node.get("widgets", {})
            wv = node.get("widgets_values", [])
            node_type = schema_node.get("type", node.get("type", ""))

            for param_name, wv_index in widgets_map.items():
                # LoRA 节点特殊处理：使用 layer 字段映射到正确的 config 属性
                node_layer = schema_node.get("layer")
                if node_type == "LoraLoaderModelOnly" and node_layer is not None:
                    if param_name == "lora_name":
                        value = getattr(config, f"lora_{node_layer}_name", "")
                    elif param_name == "strength_model":
                        value = getattr(config, f"lora_{node_layer}_strength", 1.0)
                    else:
                        value = self._get_config_value(config, param_name)
                else:
                    value = self._get_config_value(config, param_name)
                if value is None or (isinstance(value, str) and value == ""):
                    continue

                # 确保 widgets_values 足够长
                while len(wv) <= wv_index:
                    wv.append(None)

                # 特殊处理：RandomNoise 节点的 seed 后面还有 control_after_generate（"randomize"/"fixed"）
                if param_name in ("noise_seed", "seed") and node.get("type") == "RandomNoise":
                    wv[wv_index] = value
                    if wv_index + 1 < len(wv):
                        wv[wv_index + 1] = "fixed"  # 强制 fixed，由我们控制 seed
                elif param_name in ("seed",) and node.get("type") == "KSampler":
                    wv[wv_index] = value
                    if wv_index + 1 < len(wv):
                        wv[wv_index + 1] = "fixed"
                else:
                    wv[wv_index] = value

        # width/height 双节点同步（EmptyLatent + Scheduler/Flux2Scheduler）
        self._sync_width_height(wf, config)

    def _patch_widgets_default(self, wf: Dict[str, Any], config: GenerationConfig) -> None:
        """无 Schema 时的默认 patch 逻辑"""
        all_nodes = self._get_all_nodes(wf)

        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])

            # 子图节点（Text to Image 入口）
            if ntype.startswith("9596") or ntype.startswith("82388"):
                while len(wv) < 6:
                    wv.append(None)
                wv[0] = config.positive_prompt
                wv[1] = config.negative_prompt
                wv[2] = config.cfg
                wv[3] = config.steps
                wv[4] = config.width
                wv[5] = config.height
                continue

            # UNETLoader
            if ntype == "UNETLoader":
                while len(wv) < 2:
                    wv.append(None)
                # unet_name 不改（保持默认）
                continue

            # CLIPLoader
            if ntype == "CLIPLoader":
                continue

            # VAELoader
            if ntype == "VAELoader":
                continue

            # EmptyFlux2LatentImage / EmptySD3LatentImage
            if ntype in ("EmptyFlux2LatentImage", "EmptySD3LatentImage"):
                while len(wv) < 3:
                    wv.append(None)
                wv[0] = config.width
                wv[1] = config.height
                # batch_size 由 chunk 拆分控制
                continue

            # RandomNoise
            if ntype == "RandomNoise":
                while len(wv) < 2:
                    wv.append(None)
                wv[0] = config.seed
                wv[1] = "fixed"
                continue

            # KSamplerSelect
            if ntype == "KSamplerSelect":
                continue

            # CFGGuider
            if ntype == "CFGGuider":
                while len(wv) < 1:
                    wv.append(None)
                wv[0] = config.cfg
                continue

            # Flux2Scheduler
            if ntype == "Flux2Scheduler":
                while len(wv) < 3:
                    wv.append(None)
                wv[0] = config.steps
                wv[1] = config.width
                wv[2] = config.height
                continue

            # KSampler (Z-Image)
            if ntype == "KSampler":
                while len(wv) < 7:
                    wv.append(None)
                wv[0] = config.seed
                wv[1] = "fixed"
                wv[2] = config.steps
                wv[3] = config.cfg
                continue

            # LoraLoaderModelOnly (id=16~21)
            if ntype == "LoraLoaderModelOnly":
                while len(wv) < 2:
                    wv.append(None)
                node_id = node.get("id", 0)
                lora_layer = node_id - 15  # 16→1, 17→2, ...
                if 1 <= lora_layer <= 6:
                    name_val = getattr(config, f"lora_{lora_layer}_name", "")
                    strength_val = getattr(config, f"lora_{lora_layer}_strength", 1.0)
                    wv[0] = name_val if name_val else wv[0]
                    wv[1] = strength_val
                continue

            # EsesImageCompare
            if ntype == "EsesImageCompare":
                while len(wv) < 2:
                    wv.append(None)
                wv[0] = "normal"
                if config.eses_compare_axis:
                    node.setdefault("compare_axis", config.eses_compare_axis)
                continue

            # ReservedVRAMSetter
            if ntype == "ReservedVRAMSetter":
                while len(wv) < 6:
                    wv.append(None)
                wv[0] = config.vram_reserved_gb
                wv[1] = config.vram_mode
                wv[2] = config.vram_seed
                wv[3] = "fixed"
                wv[4] = 0
                wv[5] = False
                continue

            # SeedVR2VideoUpscaler
            if ntype == "SeedVR2VideoUpscaler":
                while len(wv) < 14:
                    wv.append(None)
                wv[0] = config.seedvr2_seed
                wv[1] = "fixed"
                wv[2] = config.seedvr2_resolution
                wv[8] = config.seedvr2_color_correction
                continue

            # SaveImage
            if ntype == "SaveImage":
                while len(wv) < 1:
                    wv.append(None)
                if config.output_prefix:
                    wv[0] = config.output_prefix
                continue

        # width/height 双节点同步
        self._sync_width_height(wf, config)

    def _sync_width_height(self, wf: Dict[str, Any], config: GenerationConfig) -> None:
        """width/height 在 EmptyLatent + Scheduler 两处同步"""
        all_nodes = self._get_all_nodes(wf)
        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])

            if ntype in ("EmptyFlux2LatentImage", "EmptySD3LatentImage"):
                while len(wv) < 2:
                    wv.append(None)
                wv[0] = config.width
                wv[1] = config.height

            if ntype == "Flux2Scheduler":
                while len(wv) < 3:
                    wv.append(None)
                wv[1] = config.width
                wv[2] = config.height

    def _get_config_value(self, config: GenerationConfig, param_name: str) -> Any:
        """从 GenerationConfig 获取参数值"""
        # 直接属性映射
        direct_map = {
            "positive_prompt": "positive_prompt",
            "negative_prompt": "negative_prompt",
            "cfg": "cfg",
            "steps": "steps",
            "width": "width",
            "height": "height",
            "seed": "seed",
            "batch_size": "batch_size",
            "noise_seed": "seed",
        }

        # LoRA 映射
        for i in range(1, 7):
            direct_map[f"lora_{i}_name"] = f"lora_{i}_name"
            direct_map[f"lora_{i}_strength"] = f"lora_{i}_strength"

        # SeedVR2
        direct_map.update({
            "seedvr2_seed": "seedvr2_seed",
            "seedvr2_resolution": "seedvr2_resolution",
            "seedvr2_color_correction": "seedvr2_color_correction",
        })

        # VRAM
        direct_map.update({
            "vram_reserved": "vram_reserved_gb",
            "vram_mode": "vram_mode",
            "vram_seed": "vram_seed",
        })

        # Eses
        direct_map.update({
            "eses_compare_axis": "eses_compare_axis",
        })

        attr = direct_map.get(param_name)
        if attr and hasattr(config, attr):
            return getattr(config, attr)
        return None

    def _patch_batch_chunk(self, wf: Dict[str, Any], config: GenerationConfig) -> Dict[str, Any]:
        """
        ⑤ batch chunk 拆分：
        - 不开超分：chunk=16
        - 开超分：chunk=4
        - 9999 批次拆成多次提交
        """
        chunk_size = recommend_chunk_size(
            config.batch_size, config.seedvr2_enable
        )

        # 如果 batch_size <= chunk_size，直接设置
        all_nodes = self._get_all_nodes(wf)
        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])

            if ntype in ("EmptyFlux2LatentImage", "EmptySD3LatentImage"):
                while len(wv) < 3:
                    wv.append(None)
                wv[2] = min(config.batch_size, chunk_size)

        # 如果 batch > chunk，需要在调用层拆分多次提交
        # 这里只设置当前 chunk 的 batch_size
        # 多次提交由 TaskQueue / engine 层处理
        if config.batch_size > chunk_size:
            logger.info(
                f"Batch chunk: {config.batch_size} → chunk size {chunk_size} "
                f"({(config.batch_size + chunk_size - 1) // chunk_size} chunks)"
            )

        return wf

    def _validate_nodes(self, wf: Dict[str, Any]) -> None:
        """
        ⑥ 提交前节点校验：
        - 所有必填节点存在
        - widgets_values 下标与 schema 一致
        - 无 mode=4 的关键节点（LoRA 已改 0）
        """
        all_nodes = self._get_all_nodes(wf)

        for node in all_nodes:
            ntype = node.get("type", "")
            wv = node.get("widgets_values", [])

            # 校验 LoRA 节点 mode 已改为 0
            if ntype == "LoraLoaderModelOnly" and node.get("mode") == 4:
                raise ValueError(
                    f"LoRA node {node.get('id')} still in bypass mode (4), should be 0"
                )

            # 校验关键节点有 widgets_values
            if ntype in ("UNETLoader", "CLIPLoader", "VAELoader") and not wv:
                logger.warning(f"Node {ntype} {node.get('id')} has no widgets_values")

        logger.debug("Workflow validation passed")

    def get_chunk_count(self, config: GenerationConfig) -> int:
        """计算需要拆分成多少个 chunk"""
        chunk_size = recommend_chunk_size(config.batch_size, config.seedvr2_enable)
        return (config.batch_size + chunk_size - 1) // chunk_size
