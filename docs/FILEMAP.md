# FILEMAP.md — Image_MultiModel 文件结构清单

> 本文件由 `scripts/update_docs.py` 维护末尾 AUTO-SYNC 标记；
> 目录结构描述以实际仓库树为准（自动生成，噪声/构建/资产大文件已过滤）。

## 顶层

| 类型 | 条目 |
|---|---|
| 目录 | `app/` |
| 目录 | `comfy_kernel/` |
| 目录 | `data/` |
| 目录 | `demo/` |
| 目录 | `docs/` |
| 目录 | `examples/` |
| 目录 | `logs/` |
| 目录 | `model/` |
| 目录 | `outputs/` |
| 目录 | `perf/` |
| 目录 | `prototypes/` |
| 目录 | `scripts/` |
| 目录 | `tests/` |
| 目录 | `workflows/` |
| 文件 | `AGENTS.md` |
| 文件 | `CHANGELOG.md` |
| 文件 | `CODE_OF_CONDUCT.md` |
| 文件 | `CONTRIBUTING.md` |
| 文件 | `Dockerfile` |
| 文件 | `LICENSE` |
| 文件 | `LOCAL_RULES.md` |
| 文件 | `README.md` |
| 文件 | `SECURITY.md` |
| 文件 | `config.yaml` |
| 文件 | `docker-compose.yml` |
| 文件 | `install.bat` |
| 文件 | `install.sh` |
| 文件 | `pyproject.toml` |
| 文件 | `release-please-config.json` |
| 文件 | `requirements-lock.txt` |
| 文件 | `requirements.txt` |
| 文件 | `start.bat` |
| 文件 | `start.sh` |

## `app/`

子目录：`integrated_app`

- `clean_launch.py`
- `install.bat`
- `start.bat`

## `app\integrated_app/`

子目录：`comfy`、`locales`、`middleware`、`native`、`preprocessors`、`routes`、`security`、`services`、`static`、`templates`、`utils`

- `__init__.py`
- `app_server.py`
- `checkpoint.py`
- `config.py`
- `config_models.py`
- `engine_interface.py`
- `exceptions.py`
- `gpu_utils.py`
- `history_db.py`
- `i18n.py`
- `mcp_server.py`
- `model_manager.py`
- `model_registry.py`
- `prompt_expander.py`
- `spec.py`
- `sse.py`
- `task_queue.py`
- `watermark.py`
- `watermark_gpu.py`

## `app\integrated_app\comfy/`

子目录：`schemas`

## `app\integrated_app\locales/`

- `en.json`
- `ja.json`
- `ko.json`
- `zh-tw.json`
- `zh.json`

## `app\integrated_app\middleware/`

- `__init__.py`
- `csrf.py`
- `error_handler.py`
- `rate_limit.py`
- `request_id.py`

## `app\integrated_app\native/`

- `__init__.py`
- `compares.py`
- `diffusers_engine.py`
- `engine.py`
- `executor.py`
- `lora.py`
- `output_pipeline.py`
- `preview.py`
- `seedvr.py`
- `source.py`
- `vram.py`

## `app\integrated_app\preprocessors/`

- `__init__.py`
- `canny.py`
- `midas.py`
- `openpose.py`

## `app\integrated_app\routes/`

- `__init__.py`
- `config_routes.py`
- `engine_routes.py`
- `generate_routes.py`
- `output_routes.py`
- `preprocess_routes.py`
- `preset_routes.py`
- `prompt_routes.py`
- `safety_routes.py`
- `system_routes.py`
- `task_routes.py`

## `app\integrated_app\security/`

- `__init__.py`
- `content_filter.py`
- `integrity_manifest.json`
- `integrity_selfcheck.py`
- `magic_check.py`
- `path_guard.py`

## `app\integrated_app\services/`

- `__init__.py`
- `seedvr2_service.py`

## `app\integrated_app\static/`

子目录：`css`、`images`、`js`

## `app\integrated_app\templates/`

子目录：`components`

- `base.html`
- `index.html`

## `app\integrated_app\utils/`

## `comfy_kernel/`

子目录：`alembic_db`、`api_server`、`app`、`blueprints`、`comfy`、`comfy_api`、`comfy_api_nodes`、`comfy_config`、`comfy_execution`、`comfy_extras`、`custom_nodes`、`input`、`middleware`、`models`、`output`、`script_examples`、`tests`、`tests-unit`、`utils`

- `AGENTS.md`
- `CODEOWNERS`
- `COMPLIANCE-README.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `QUANTIZATION.md`
- `README.md`
- `SECURITY.md`
- `UPGRADE_STRATEGY.md`
- `alembic.ini`
- `comfyui_version.py`
- `cuda_malloc.py`
- `execution.py`
- `extra_model_paths.yaml.example`
- `folder_paths.py`
- `hook_breaker_ac10a0.py`
- `latent_preview.py`
- `main.py`
- `manager_requirements.txt`
- `node_helpers.py`
- `nodes.py`
- `openapi.yaml`
- `protocol.py`
- `pyproject.toml`
- `pytest.ini`
- `requirements.txt`
- `server.py`

## `comfy_kernel\alembic_db/`

子目录：`versions`

- `README.md`
- `env.py`
- `script.py.mako`

## `comfy_kernel\alembic_db\versions/`

- `0001_assets.py`
- `0002_merge_to_asset_references.py`
- `0003_add_metadata_job_id.py`
- `0004_drop_tag_type.py`
- `0005_allow_case_sensitive_tags.py`
- `0006_add_loader_path.py`

## `comfy_kernel\api_server/`

子目录：`routes`、`services`、`utils`

- `__init__.py`

## `comfy_kernel\api_server\routes/`

子目录：`internal`

- `__init__.py`

## `comfy_kernel\api_server\services/`

- `__init__.py`
- `terminal_service.py`

## `comfy_kernel\api_server\utils/`

- `file_operations.py`

## `comfy_kernel\app/`

子目录：`assets`、`database`

- `__init__.py`
- `app_settings.py`
- `custom_node_manager.py`
- `frontend_management.py`
- `logger.py`
- `model_manager.py`
- `node_replace_manager.py`
- `subgraph_manager.py`
- `user_manager.py`

## `comfy_kernel\app\assets/`

子目录：`api`、`database`、`services`

- `helpers.py`
- `scanner.py`
- `seeder.py`

## `comfy_kernel\app\database/`

- `db.py`
- `models.py`

## `comfy_kernel\blueprints/`

- `Audio Generation (Stable Audio 3 Medium Base).json`
- `Audio Generation (Stable Audio 3 Medium).json`
- `Brightness and Contrast.json`
- `Canny to Image (Z-Image-Turbo).json`
- `Canny to Video (LTX 2.0).json`
- `Character Replacement (SCAIL-2 Base).json`
- `Character Replacement (SCAIL-2 Extend).json`
- `Chromatic Aberration.json`
- `Color Adjustment.json`
- `Color Balance.json`
- `Color Curves.json`
- `ControlNet (Z-Image-Turbo).json`
- `Crop Images 2x2.json`
- `Crop Images 3x3.json`
- `Depth to Image (Z-Image-Turbo).json`
- `Depth to Video (ltx 2.0).json`
- `Edge-Preserving Blur.json`
- `Film Grain.json`
- `First-Last-Frame to Video (LTX-2.3).json`
- `First-Last-Frame to Video.json`
- `Frame Interpolation.json`
- `Geometry Estimation (MoGe).json`
- `Get Any Video Frame.json`
- `Glow.json`
- `Hue and Saturation.json`
- `Image Blur.json`
- `Image Captioning (gemini).json`
- `Image Channels.json`
- `Image Depth Estimation (Depth Anything 3).json`
- `Image Depth Estimation (Lotus Depth).json`
- `Image Depth Estimation (MoGe).json`
- `Image Edit (Bernini-R).json`
- `Image Edit (FireRed Image Edit 1.1).json`
- `Image Edit (Flux.2 Dev).json`
- `Image Edit (Flux.2 Klein 4B).json`
- `Image Edit (LongCat Image Edit).json`
- `Image Edit (Qwen 2509).json`
- `Image Edit (Qwen 2511).json`
- `Image Face Detection (Mediapipe).json`
- `Image Inpainting (Flux.1 Fill Dev).json`
- `Image Inpainting (Qwen-image).json`
- `Image Levels.json`
- `Image Outpainting (Qwen-Image).json`
- `Image Segmentation (SAM3).json`
- `Image Upscale(Z-image-Turbo).json`
- `Image to Gaussian Splat (TripoSplat).json`
- `Image to Layers(Qwen-Image-Layered).json`
- `Image to Model (Hunyuan3d 2.1).json`
- `Image to Pose Map (SDPose Multi-Person).json`
- `Image to Pose Map (SDPose-OOD).json`
- `Image to Video (LTX-2.3).json`
- `Image to Video (Wan 2.2).json`
- `Merge Videos.json`
- `Pose to Image (Z-Image-Turbo).json`
- `Pose to Video (LTX 2.0).json`
- `Prompt Enhance.json`
- `Remove Background (BiRefNet).json`
- `Select Per-Line Text by Index.json`
- `Sharpen.json`
- `Split Image Grid to Tiles.json`
- `Text to Audio (ACE-Step 1.5).json`
- `Text to Image (Anima Base 1.0).json`
- `Text to Image (Anima).json`
- `Text to Image (Ernie Image Turbo).json`
- `Text to Image (Ernie Image).json`
- `Text to Image (Flux.1 Dev).json`
- `Text to Image (Flux.1 Krea Dev).json`
- `Text to Image (Flux.2 Dev).json`
- `Text to Image (Ideogram v4).json`
- `Text to Image (NetaYume Lumina).json`
- `Text to Image (Qwen-Image 2512).json`
- `Text to Image (Qwen-Image).json`
- `Text to Image (Z-Image-Base).json`
- `Text to Image (Z-Image-Turbo).json`
- `Text to Image.json`
- `Text to Video (LTX-2.3).json`
- `Text to Video (Wan 2.2).json`
- `Unsharp Mask.json`
- `Video Captioning (Gemini).json`
- `Video Depth Estimation (Depth Anything 3).json`
- `Video Depth Estimation (MoGe).json`
- `Video Edit (Bernini-R).json`
- `Video Face Detection (Mediapipe).json`
- `Video Inpaint (VOID).json`
- `Video Inpainting (Wan2.1 VACE).json`
- `Video Segmentation (SAM3).json`
- `Video Stitch.json`
- `Video Upscale(GAN x4).json`
- `Video to Pose Map (SDPose Multi-Person).json`
- `put_blueprints_here`

## `comfy_kernel\comfy/`

子目录：`audio_encoders`、`background_removal`、`cldm`、`comfy_types`、`extra_samplers`、`image_encoders`、`k_diffusion`、`ldm`、`sd1_tokenizer`、`t2i_adapter`、`taesd`、`text_encoders`、`weight_adapter`

- `bg_removal_model.py`
- `cli_args.py`
- `clip_config_bigg.json`
- `clip_model.py`
- `clip_vision.py`
- `clip_vision_config_g.json`
- `clip_vision_config_h.json`
- `clip_vision_config_vitl.json`
- `clip_vision_config_vitl_336.json`
- `clip_vision_config_vitl_336_llava.json`
- `clip_vision_siglip2_base_naflex.json`
- `clip_vision_siglip_384.json`
- `clip_vision_siglip_512.json`
- `comfy_api_env.py`
- `conds.py`
- `context_windows.py`
- `controlnet.py`
- `deploy_environment.py`
- `diffusers_convert.py`
- `diffusers_load.py`
- `float.py`
- `gligen.py`
- `hooks.py`
- `internal_logging.py`
- `latent_formats.py`
- `lora.py`
- `lora_convert.py`
- `memory_management.py`
- `model_base.py`
- `model_detection.py`
- `model_management.py`
- `model_patcher.py`
- `model_prefetch.py`
- `model_sampling.py`
- `multigpu.py`
- `nested_tensor.py`
- `ops.py`
- `options.py`
- `patcher_extension.py`
- `pinned_memory.py`
- `pixel_space_convert.py`
- `quant_ops.py`
- `rmsnorm.py`
- `sample.py`
- `sampler_helpers.py`
- `samplers.py`
- `sd.py`
- `sd1_clip.py`
- `sd1_clip_config.json`
- `sdxl_clip.py`
- `supported_models.py`
- `supported_models_base.py`
- `utils.py`

## `comfy_kernel\comfy\audio_encoders/`

- `audio_encoders.py`
- `wav2vec2.py`
- `whisper.py`

## `comfy_kernel\comfy\background_removal/`

- `birefnet.json`
- `birefnet.py`

## `comfy_kernel\comfy\cldm/`

- `cldm.py`
- `control_types.py`
- `dit_embedder.py`
- `mmdit.py`

## `comfy_kernel\comfy\comfy_types/`

子目录：`examples`

- `README.md`
- `__init__.py`
- `node_typing.py`

## `comfy_kernel\comfy\extra_samplers/`

- `uni_pc.py`

## `comfy_kernel\comfy\image_encoders/`

- `dino2.py`
- `dino2_giant.json`
- `dino2_large.json`
- `dino3.py`

## `comfy_kernel\comfy\k_diffusion/`

- `deis.py`
- `sa_solver.py`
- `sampling.py`
- `utils.py`

## `comfy_kernel\comfy\ldm/`

子目录：`ace`、`anima`、`audio`、`aura`、`boogu`、`cascade`、`chroma`、`chroma_radiance`、`cogvideo`、`cosmos`、`depth_anything_3`、`ernie`、`flux`、`genmo`、`hidream`、`hidream_o1`、`hunyuan3d`、`hunyuan3dv2_1`、`hunyuan_video`、`hydit`、`ideogram4`、`joyimage`、`kandinsky5`、`krea2`、`lens`、`lightricks`、`lumina`、`mage_flow`、`minimax`、`mmaudio`、`models`、`modules`、`moge`、`omnigen`、`pixart`、`pixeldit`、`qwen_image`、`rt_detr`、`sam3`、`seedvr`、`supir`、`triposplat`、`wan`

- `colormap.py`
- `common_dit.py`
- `util.py`

## `comfy_kernel\comfy\sd1_tokenizer/`

- `merges.txt`
- `special_tokens_map.json`
- `tokenizer_config.json`
- `vocab.json`

## `comfy_kernel\comfy\t2i_adapter/`

- `adapter.py`

## `comfy_kernel\comfy\taesd/`

- `taehv.py`
- `taesd.py`

## `comfy_kernel\comfy\text_encoders/`

子目录：`ace_lyrics_tokenizer`、`byt5_tokenizer`、`hydit_clip_tokenizer`、`llama_tokenizer`、`qwen25_tokenizer`、`qwen35_tokenizer`、`t5_pile_tokenizer`、`t5_tokenizer`

- `ace.py`
- `ace15.py`
- `ace_text_cleaners.py`
- `anima.py`
- `aura_t5.py`
- `bert.py`
- `boogu.py`
- `bpe_tokenizer.py`
- `byt5_config_small_glyph.json`
- `cogvideo.py`
- `cosmos.py`
- `ernie.py`
- `flux.py`
- `gemma4.py`
- `genmo.py`
- `gpt_oss.py`
- `hidream.py`
- `hidream_o1.py`
- `hunyuan_image.py`
- `hunyuan_video.py`
- `hydit.py`
- `hydit_clip.json`
- `ideogram4.py`
- `jina_clip_2.py`
- `joyimage.py`
- `kandinsky5.py`
- `krea2.py`
- `llama.py`
- `long_clipl.py`
- `longcat_image.py`
- `lt.py`
- `lumina2.py`
- `mage_flow.py`
- `minimax.py`
- `mt5_config_xl.json`
- `newbie.py`
- `omnigen2.py`
- `ovis.py`
- `pixart_t5.py`
- `pixeldit.py`
- `qwen35.py`
- `qwen3vl.py`
- `qwen_image.py`
- `qwen_vl.py`
- `sa3.py`
- `sa_t5.py`
- `sam3_clip.py`
- `sd2_clip.py`
- `sd2_clip_config.json`
- `sd3_clip.py`
- `spiece_tokenizer.py`
- `t5.py`
- `t5_config_base.json`
- `t5_config_xxl.json`
- `t5_old_config_xxl.json`
- `t5_pile_config_xl.json`
- `umt5_config_base.json`
- `umt5_config_xxl.json`
- `wan.py`
- `z_image.py`

## `comfy_kernel\comfy\weight_adapter/`

- `__init__.py`
- `base.py`
- `boft.py`
- `bypass.py`
- `glora.py`
- `loha.py`
- `lokr.py`
- `lora.py`
- `oft.py`

## `comfy_kernel\comfy_api/`

子目录：`input`、`input_impl`、`internal`、`latest`、`torch_helpers`、`util`、`v0_0_1`、`v0_0_2`

- `feature_flags.py`
- `generate_api_stubs.py`
- `util.py`
- `version_list.py`

## `comfy_kernel\comfy_api\input/`

- `__init__.py`
- `basic_types.py`
- `video_types.py`

## `comfy_kernel\comfy_api\input_impl/`

- `__init__.py`
- `video_types.py`

## `comfy_kernel\comfy_api\internal/`

- `__init__.py`
- `api_registry.py`
- `async_to_sync.py`
- `singleton.py`

## `comfy_kernel\comfy_api\latest/`

子目录：`_input`、`_input_impl`、`_util`、`generated`

- `__init__.py`
- `_caching.py`
- `_io.py`
- `_io_public.py`
- `_ui.py`
- `_ui_public.py`

## `comfy_kernel\comfy_api\torch_helpers/`

- `__init__.py`
- `torch_compile.py`

## `comfy_kernel\comfy_api\util/`

- `__init__.py`
- `video_types.py`

## `comfy_kernel\comfy_api\v0_0_1/`

子目录：`generated`

- `__init__.py`

## `comfy_kernel\comfy_api\v0_0_2/`

子目录：`generated`

- `__init__.py`

## `comfy_kernel\comfy_api_nodes/`

子目录：`apis`、`util`

- `__init__.py`
- `nodes_anthropic.py`
- `nodes_beeble.py`
- `nodes_bfl.py`
- `nodes_bria.py`
- `nodes_bytedance.py`
- `nodes_bytedance_llm.py`
- `nodes_elevenlabs.py`
- `nodes_gemini.py`
- `nodes_grok.py`
- `nodes_heygen.py`
- `nodes_hitpaw.py`
- `nodes_hunyuan3d.py`
- `nodes_ideogram.py`
- `nodes_kling.py`
- `nodes_krea.py`
- `nodes_ltxv.py`
- `nodes_luma.py`
- `nodes_magnific.py`
- `nodes_meshy.py`
- `nodes_minimax.py`
- `nodes_openai.py`
- `nodes_openrouter.py`
- `nodes_pixverse.py`
- `nodes_quiver.py`
- `nodes_qwen.py`
- `nodes_recraft.py`
- `nodes_reve.py`
- `nodes_rodin.py`
- `nodes_runway.py`
- `nodes_sonilo.py`
- `nodes_sora.py`
- `nodes_sync_so.py`
- `nodes_topaz.py`
- `nodes_tripo.py`
- `nodes_veo2.py`
- `nodes_vidu.py`
- `nodes_wan.py`
- `nodes_wavespeed.py`

## `comfy_kernel\comfy_api_nodes\apis/`

- `__init__.py`
- `anthropic.py`
- `beeble.py`
- `bfl.py`
- `bria.py`
- `bytedance.py`
- `bytedance_llm.py`
- `elevenlabs.py`
- `gemini.py`
- `grok.py`
- `heygen.py`
- `hitpaw.py`
- `hunyuan3d.py`
- `ideogram.py`
- `kling.py`
- `krea.py`
- `luma.py`
- `magnific.py`
- `meshy.py`
- `minimax.py`
- `openai.py`
- `openrouter.py`
- `pixverse.py`
- `quiver.py`
- `qwen.py`
- `recraft.py`
- `reve.py`
- `rodin.py`
- `runway.py`
- `sync_so.py`
- `topaz.py`
- `tripo.py`
- `veo.py`
- `vidu.py`
- `wan.py`
- `wavespeed.py`

## `comfy_kernel\comfy_api_nodes\util/`

- `__init__.py`
- `_helpers.py`
- `client.py`
- `common_exceptions.py`
- `conversions.py`
- `download_helpers.py`
- `request_logger.py`
- `upload_helpers.py`
- `validation_utils.py`

## `comfy_kernel\comfy_config/`

- `config_parser.py`
- `types.py`

## `comfy_kernel\comfy_execution/`

- `asset_enrichment.py`
- `cache_provider.py`
- `caching.py`
- `graph.py`
- `graph_utils.py`
- `jobs.py`
- `progress.py`
- `utils.py`
- `validation.py`

## `comfy_kernel\comfy_extras/`

子目录：`chainner_models`、`frame_interpolation_models`、`mediapipe`

- `color_util.py`
- `compositor_blend.py`
- `nodes_ace.py`
- `nodes_advanced_samplers.py`
- `nodes_align_your_steps.py`
- `nodes_apg.py`
- `nodes_ar_video.py`
- `nodes_attention_multiply.py`
- `nodes_audio.py`
- `nodes_audio_encoder.py`
- `nodes_bernini.py`
- `nodes_bg_removal.py`
- `nodes_boogu.py`
- `nodes_bounding_boxes.py`
- `nodes_camera_trajectory.py`
- `nodes_canny.py`
- `nodes_cfg.py`
- `nodes_chroma_radiance.py`
- `nodes_clip_sdxl.py`
- `nodes_color.py`
- `nodes_compositing.py`
- `nodes_compositor.py`
- `nodes_cond.py`
- `nodes_context_windows.py`
- `nodes_controlnet.py`
- `nodes_cosmos.py`
- `nodes_curve.py`
- `nodes_custom_sampler.py`
- `nodes_dataset.py`
- `nodes_depth_anything_3.py`
- `nodes_differential_diffusion.py`
- `nodes_easycache.py`
- `nodes_edit_model.py`
- `nodes_eps.py`
- `nodes_flux.py`
- `nodes_frame_interpolation.py`
- `nodes_freelunch.py`
- `nodes_fresca.py`
- `nodes_gaussian_splat.py`
- `nodes_gits.py`
- `nodes_glsl.py`
- `nodes_hidream.py`
- `nodes_hidream_o1.py`
- `nodes_hooks.py`
- `nodes_hunyuan.py`
- `nodes_hunyuan3d.py`
- `nodes_hypernetwork.py`
- `nodes_hypertile.py`
- `nodes_ideogram4.py`
- `nodes_image_compare.py`
- `nodes_images.py`
- `nodes_ip2p.py`
- `nodes_joyimage.py`
- `nodes_json_prompt.py`
- `nodes_kandinsky5.py`
- `nodes_latent.py`
- `nodes_load_3d.py`
- `nodes_logic.py`
- `nodes_lora_debug.py`
- `nodes_lora_extract.py`
- `nodes_lotus.py`
- `nodes_lt.py`
- `nodes_lt_audio.py`
- `nodes_lt_upsampler.py`
- `nodes_lumina2.py`
- `nodes_mage.py`
- `nodes_mahiro.py`
- `nodes_mask.py`
- `nodes_math.py`
- `nodes_mediapipe.py`
- `nodes_minimax_h3.py`
- `nodes_mochi.py`
- `nodes_model_advanced.py`
- `nodes_model_downscale.py`
- `nodes_model_merging.py`
- `nodes_model_merging_model_specific.py`
- `nodes_model_patch.py`
- `nodes_moge.py`
- `nodes_morphology.py`
- `nodes_multigpu.py`
- `nodes_nag.py`
- `nodes_nop.py`
- `nodes_number_convert.py`
- `nodes_optimalsteps.py`
- `nodes_pag.py`
- `nodes_painter.py`
- `nodes_perpneg.py`
- `nodes_photomaker.py`
- `nodes_pid.py`
- `nodes_pixart.py`
- `nodes_post_processing.py`
- `nodes_preview_any.py`
- `nodes_primitive.py`
- `nodes_qwen.py`
- `nodes_rebatch.py`
- `nodes_replacements.py`
- `nodes_resolution.py`
- `nodes_rope.py`
- `nodes_rtdetr.py`
- `nodes_sag.py`
- `nodes_sam3.py`
- `nodes_save_3d.py`
- `nodes_scail.py`
- `nodes_sd3.py`
- `nodes_sdpose.py`
- `nodes_sdupscale.py`
- `nodes_seed.py`
- `nodes_seedvr.py`
- `nodes_slg.py`
- `nodes_stable3d.py`
- `nodes_stable_cascade.py`
- `nodes_string.py`
- `nodes_tcfg.py`
- `nodes_text.py`
- `nodes_text_overlay.py`
- `nodes_textgen.py`
- `nodes_tomesd.py`
- `nodes_toolkit.py`
- `nodes_torch_compile.py`
- `nodes_train.py`
- `nodes_triposplat.py`
- `nodes_upscale_model.py`
- `nodes_video.py`
- `nodes_video_model.py`
- `nodes_void.py`
- `nodes_wan.py`
- `nodes_wandancer.py`
- `nodes_wanmove.py`
- `nodes_webcam.py`
- `nodes_zimage.py`
- `void_noise_warp.py`

## `comfy_kernel\comfy_extras\chainner_models/`

- `model_loading.py`

## `comfy_kernel\comfy_extras\frame_interpolation_models/`

- `film_net.py`
- `ifnet.py`

## `comfy_kernel\comfy_extras\mediapipe/`

- `face_geometry.py`
- `face_landmarker.py`

## `comfy_kernel\custom_nodes/`

- `example_node.py.example`
- `websocket_image_save.py`

## `comfy_kernel\input/`

## `comfy_kernel\middleware/`

- `__init__.py`
- `cache_middleware.py`

## `comfy_kernel\models/`

子目录：`audio_encoders`、`background_removal`、`checkpoints`、`clip`、`clip_vision`、`configs`、`controlnet`、`detection`、`diffusers`、`diffusion_models`、`embeddings`、`frame_interpolation`、`geometry_estimation`、`gligen`、`hypernetworks`、`latent_upscale_models`、`loras`、`model_patches`、`optical_flow`、`photomaker`、`style_models`、`text_encoders`、`unet`、`upscale_models`、`vae`、`vae_approx`

## `comfy_kernel\models\audio_encoders/`

- `put_audio_encoder_models_here`

## `comfy_kernel\models\background_removal/`

- `put_background_removal_models_here`

## `comfy_kernel\models\checkpoints/`

- `put_checkpoints_here`

## `comfy_kernel\models\clip/`

- `put_clip_or_text_encoder_models_here`

## `comfy_kernel\models\clip_vision/`

- `put_clip_vision_models_here`

## `comfy_kernel\models\configs/`

- `anything_v3.yaml`
- `v1-inference.yaml`
- `v1-inference_clip_skip_2.yaml`
- `v1-inference_clip_skip_2_fp16.yaml`
- `v1-inference_fp16.yaml`
- `v1-inpainting-inference.yaml`
- `v2-inference-v.yaml`
- `v2-inference-v_fp32.yaml`
- `v2-inference.yaml`
- `v2-inference_fp32.yaml`
- `v2-inpainting-inference.yaml`

## `comfy_kernel\models\controlnet/`

- `put_controlnets_and_t2i_here`

## `comfy_kernel\models\detection/`

- `put_detection_models_here`

## `comfy_kernel\models\diffusers/`

- `put_diffusers_models_here`

## `comfy_kernel\models\diffusion_models/`

- `put_diffusion_model_files_here`

## `comfy_kernel\models\embeddings/`

- `put_embeddings_or_textual_inversion_concepts_here`

## `comfy_kernel\models\frame_interpolation/`

- `put_frame_interpolation_models_here`

## `comfy_kernel\models\geometry_estimation/`

- `put_geometry_estimation_models_here`

## `comfy_kernel\models\gligen/`

- `put_gligen_models_here`

## `comfy_kernel\models\hypernetworks/`

- `put_hypernetworks_here`

## `comfy_kernel\models\latent_upscale_models/`

- `put_latent_upscale_models_here`

## `comfy_kernel\models\loras/`

- `put_loras_here`

## `comfy_kernel\models\model_patches/`

- `put_model_patches_here`

## `comfy_kernel\models\optical_flow/`

- `put_optical_flow_models_here`

## `comfy_kernel\models\photomaker/`

- `put_photomaker_models_here`

## `comfy_kernel\models\style_models/`

- `put_t2i_style_model_here`

## `comfy_kernel\models\text_encoders/`

- `put_text_encoder_files_here`

## `comfy_kernel\models\unet/`

- `put_unet_files_here`

## `comfy_kernel\models\upscale_models/`

- `put_esrgan_and_other_upscale_models_here`

## `comfy_kernel\models\vae/`

- `put_vae_here`

## `comfy_kernel\models\vae_approx/`

- `put_taesd_encoder_pth_and_taesd_decoder_pth_here`

## `comfy_kernel\output/`

- `_output_images_will_be_put_here`

## `comfy_kernel\script_examples/`

- `basic_api_example.py`
- `websockets_api_example.py`
- `websockets_api_example_ws_images.py`

## `comfy_kernel\tests/`

子目录：`compare`、`execution`、`inference`

- `README.md`
- `__init__.py`
- `conftest.py`
- `test_asset_seeder.py`

## `comfy_kernel\tests-unit/`

子目录：`app_test`、`assets_test`、`comfy_api_nodes_test`、`comfy_api_test`、`comfy_extras_test`、`comfy_quant`、`comfy_test`、`execution_test`、`folder_paths_test`、`jobs_cancel_test`、`prompt_server_test`、`security_test`、`seeder_test`、`server`、`server_test`、`utils`

- `README.md`
- `deploy_environment_test.py`
- `feature_flags_test.py`
- `requirements.txt`
- `websocket_feature_flags_test.py`

## `comfy_kernel\tests-unit\app_test/`

- `__init__.py`
- `custom_node_manager_test.py`
- `frontend_manager_test.py`
- `model_manager_test.py`
- `node_replace_manager_test.py`
- `test_migrations.py`
- `user_manager_system_user_test.py`

## `comfy_kernel\tests-unit\assets_test/`

子目录：`queries`、`services`

- `conftest.py`
- `helpers.py`
- `test_assets_missing_sync.py`
- `test_crud.py`
- `test_downloads.py`
- `test_file_utils.py`
- `test_list_cursor.py`
- `test_list_filter.py`
- `test_metadata_filters.py`
- `test_prompt_id_enforcement.py`
- `test_prune_orphaned_assets.py`
- `test_sync_references.py`
- `test_tags_api.py`
- `test_uploads.py`

## `comfy_kernel\tests-unit\comfy_api_nodes_test/`

- `audio_conversions_test.py`

## `comfy_kernel\tests-unit\comfy_api_test/`

- `input_impl_test.py`
- `multicombo_serialization_test.py`
- `video_bit_depth_test.py`
- `video_types_test.py`

## `comfy_kernel\tests-unit\comfy_extras_test/`

- `__init__.py`
- `compositor_blend_fixture_gen.py`
- `compositor_blend_golden.json`
- `compositor_blend_test.py`
- `compositor_node_test.py`
- `image_stitch_test.py`
- `nodes_math_test.py`
- `nodes_number_convert_test.py`
- `nodes_preview_any_test.py`
- `test_seedvr2_conditioning.py`
- `test_seedvr2_nodes.py`
- `test_seedvr2_post_processing.py`
- `test_seedvr2_temporal_chunk.py`

## `comfy_kernel\tests-unit\comfy_quant/`

- `test_mixed_precision.py`

## `comfy_kernel\tests-unit\comfy_test/`

- `folder_path_test.py`
- `model_detection_test.py`
- `seedvr_vae_forward_test.py`
- `test_seedvr2_dtype.py`
- `test_seedvr2_internals.py`
- `test_seedvr2_model.py`
- `test_seedvr2_vae_decode.py`
- `test_seedvr2_vae_tiled.py`
- `test_vae_decode_tiled_nested.py`

## `comfy_kernel\tests-unit\execution_test/`

- `preview_method_override_test.py`
- `test_cache_provider.py`
- `test_enrich_output.py`
- `validate_node_input_test.py`

## `comfy_kernel\tests-unit\folder_paths_test/`

- `__init__.py`
- `filter_by_content_types_test.py`
- `misc_test.py`
- `system_user_test.py`

## `comfy_kernel\tests-unit\jobs_cancel_test/`

- `__init__.py`
- `jobs_cancel_test.py`

## `comfy_kernel\tests-unit\prompt_server_test/`

- `__init__.py`
- `system_user_endpoint_test.py`
- `user_manager_test.py`

## `comfy_kernel\tests-unit\security_test/`

- `__init__.py`
- `test_ghsa_779p_02_preview_traversal.py`
- `test_ghsa_779p_03_annotated_traversal.py`
- `test_ghsa_779p_04_userdata_xss.py`
- `test_ghsa_779p_05_dangerous_content_types.py`
- `test_ghsa_779p_06_inline_svg_image_dest.py`

## `comfy_kernel\tests-unit\seeder_test/`

- `test_seeder.py`

## `comfy_kernel\tests-unit\server/`

子目录：`utils`

## `comfy_kernel\tests-unit\server_test/`

- `test_cache_control.py`

## `comfy_kernel\tests-unit\utils/`

- `extra_config_test.py`
- `json_util_test.py`

## `comfy_kernel\tests\compare/`

- `conftest.py`
- `test_quality.py`

## `comfy_kernel\tests\execution/`

子目录：`testing_nodes`

- `extra_model_paths.yaml`
- `test_async_nodes.py`
- `test_execution.py`
- `test_jobs.py`
- `test_preview_method.py`
- `test_progress_isolation.py`
- `test_public_api.py`

## `comfy_kernel\tests\inference/`

子目录：`graphs`

- `__init__.py`
- `test_inference.py`

## `comfy_kernel\utils/`

- `__init__.py`
- `extra_config.py`
- `install_util.py`
- `json_util.py`
- `mime_types.py`

## `data/`

子目录：`cache`、`checkpoints`、`uploads`

- `history.db-shm`
- `history.db-wal`

## `data\cache/`

子目录：`thumbs`

## `data\cache\thumbs/`

## `data\checkpoints/`

## `data\uploads/`

## `demo/`

子目录：`assets`

- `README.md`
- `index.html`

## `demo\assets/`

子目录：`gallery`

## `demo\assets\gallery/`

## `docs/`

子目录：`adr`、`plans`、`project`、`repo-analysis`、`reports`

- `COMPLIANCE_CHECKLIST.md`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `整理记录_20260823.md`

## `docs\adr/`

- `0001-native-engine-comfy-kernel.md`
- `0002-docs-reorganization-20260823.md`
- `README.md`

## `docs\plans/`

- `COMFYUI-INDEPENDENCE-PLAN.md`
- `CROSS_PROJECT_PATH_GUIDE.md`
- `DEPLOYMENT.md`
- `JINJA2_REFACTOR_PLAN.md`
- `MASTER_PLAN.md`
- `WEBAPP_GUIDE.md`
- `全功能实施指南.md`

## `docs\project/`

- `API.md`
- `ARCHITECTURE.md`
- `PATH-CONFIGURATION.md`
- `PRD.md`

## `docs\repo-analysis/`

- `8 仓库对 Image_MultiModel 项目的持续价值分析.md`
- `CLIP_技术学习报告.md`
- `ComfyUI_技术学习报告.md`
- `Fooocus_技术学习报告.md`
- `InvokeAI_技术学习报告.md`
- `diffusers_技术学习报告.md`
- `generative-models_技术学习报告.md`
- `sd-webui-controlnet_技术学习报告.md`
- `stable-diffusion-webui_技术学习报告.md`
- `综合技术学习报告.md`

## `docs\reports/`

- `AUDIT_REPORT_v2.md`
- `CI-LESSONS.md`
- `LOGGING_AUDIT_REPORT.md`
- `LOGGING_AUDIT_SUMMARY_REPORT.md`
- `REMAINING_TASKS_REPORT.md`
- `TEST_AUDIT.md`
- `功能实现状态分析报告.md`
- `项目健康度评估报告.md`

## `examples/`

- `01_text_to_image.py`
- `02_batch_generate.py`
- `03_sse_progress.py`
- `04_list_history.py`
- `05_apply_preset.py`
- `README.md`
- `prompts.txt`

## `logs/`

## `model/`

子目录：`loras`、`text_encoders`、`unet`、`vae`

- `README.md`

## `model\loras/`

- `put_loras_here`

## `model\text_encoders/`

子目录：`FLUX.1-dev`、`FLUX.2-klein-9b`、`Z_image(turbo)`

- `put_text_encoders_here`

## `model\text_encoders\FLUX.1-dev/`

## `model\text_encoders\FLUX.2-klein-9b/`

## `model\text_encoders\Z_image(turbo)/`

## `model\unet/`

子目录：`FLUX.1-dev-fp8`、`FLUX.2-klein-9b-fp8`、`Z-image-bf16`、`Z-image_turbo-bf16`

- `put_unet_here`

## `model\unet\FLUX.1-dev-fp8/`

## `model\unet\FLUX.2-klein-9b-fp8/`

## `model\unet\Z-image-bf16/`

## `model\unet\Z-image_turbo-bf16/`

## `model\vae/`

子目录：`FLUX.1-dev(Z-image(turbo))`、`FLUX.2-klein-9b`

- `put_vae_here`

## `model\vae\FLUX.1-dev(Z-image(turbo))/`

## `model\vae\FLUX.2-klein-9b/`

## `outputs/`

## `perf/`

子目录：`results`

- `monitoring_plan.md`

## `perf\results/`

## `prototypes/`

子目录：`figma-refactor`、`style-compare`

- `batch.html`
- `generate.html`
- `history.html`
- `index.html`
- `settings.html`
- `status.html`

## `prototypes\figma-refactor/`

子目录：`layout-compare`

- `batch.html`
- `gallery.html`
- `generate.html`
- `history.html`
- `ia-map.html`
- `presets.html`

## `prototypes\figma-refactor\layout-compare/`

- `a-creative.html`
- `b-split.html`
- `c-collapsible.html`
- `d-drawer.html`
- `e-wizard.html`
- `f-pipeline.html`
- `g-master-detail.html`
- `h-minimal.html`

## `prototypes\style-compare/`

- `figma.html`

## `scripts/`

子目录：`git-hooks`

- `_poll_task.py`
- `benchmark.py`
- `capture-screenshots.bat`
- `check_local.py`
- `check_spec_refs.py`
- `check_wcag.py`
- `final_ui_update.py`
- `fix_encoding_diag.py`
- `generate_integrity_manifest.py`
- `init_watermark_key.py`
- `install-hooks.ps1`
- `migrate_outputs.py`
- `pack_portable.ps1`
- `perf_monitor.py`
- `render_pages.py`
- `setup_symlinks.ps1`
- `test_portable_mode.py`
- `update_changelog.py`
- `verify_watermark.py`

## `scripts\git-hooks/`

## `tests/`

子目录：`e2e`、`frontend`

- `__init__.py`
- `capture-screenshots.js`
- `conftest.py`
- `factories.py`
- `package-lock.json`
- `package.json`
- `test_api_contract.py`
- `test_chaos_engineering.py`
- `test_checkpoint.py`
- `test_concurrent_db.py`
- `test_config.py`
- `test_config_save.py`
- `test_content_filter.py`
- `test_cors.py`
- `test_engine_routes.py`
- `test_error_handler.py`
- `test_error_handler_edge.py`
- `test_forward_batch_and_cancel.py`
- `test_forward_path_api.py`
- `test_generate_routes.py`
- `test_history_db_outputs.py`
- `test_history_db_recovery.py`
- `test_hypothesis.py`
- `test_i18n.py`
- `test_i18n_backend.py`
- `test_i18n_coverage.py`
- `test_i18n_extra.py`
- `test_mcp_server.py`
- `test_middleware.py`
- `test_model_manager.py`
- `test_model_registry.py`
- `test_native_batch_cancel.py`
- `test_native_compares.py`
- `test_native_coverage.py`
- `test_native_lora.py`
- `test_native_preview.py`
- `test_native_security.py`
- `test_native_seedvr.py`
- `test_native_vram.py`
- `test_native_zimage_poc.py`
- `test_output_routes.py`
- `test_path_guard_attacks.py`
- `test_preprocessors.py`
- `test_prompt_expander.py`
- `test_route_coverage.py`
- `test_security_audit.py`
- `test_spec.py`
- `test_sql_injection.py`
- `test_sse.py`
- `test_system_routes.py`
- `test_task_queue_cancel.py`
- `test_verify_watermark_cli.py`
- `test_vram_estimation.py`
- `test_watermark.py`

## `tests\e2e/`

子目录：`pages`

- `conftest.py`
- `test_core_user_flows.py`
- `test_engine_switch.py`
- `test_generate_progress.py`
- `test_generation_flow.py`
- `test_i18n_switch.py`

## `tests\e2e\pages/`

- `__init__.py`
- `base_page.py`
- `generate_page.py`
- `home_page.py`

## `tests\frontend/`

- `README.md`
- `smoke.js`

## `workflows/`

- `Z_image_turbo.json`
- `flux1_dev_fp8.json`
- `flux2_klein_9b.json`

<!-- AUTO-SYNC 2026-08-27 15:16 : +2 ~5 -0 -->
