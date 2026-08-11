# Image_MultiModel 性能监控计划

## 📊 监控指标
- **API 响应时间**: 健康检查和基础 API 调用耗时
- **图像生成延迟**: （可选扩展）从请求到第一张图生成的时间
- **队列处理能力**: （可选扩展）批量任务的吞吐量

## 🚀 使用方法
`ash
# 1. 启动 Image 生成服务
python -m uvicorn bin.integrated_app.app_server:app --host 127.0.0.1 --port 8080

# 2. 运行监控
python perf_monitor.py
`

## 📁 输出位置
结果保存在 ./perf/results/benchmark_YYYYMMDD_HHMMSS.json

## 📋 执行建议
- **频率**: CSS 布局调整或前端优化后手动运行
- **视觉对比**: 结合实际 UI 截图确认 Grid 布局效果
- **资源监控**: 同时观察浏览器开发者工具中的 Performance 标签

## ⚠️ 注意事项
- 仅测量 API 层面，如需完整用户体验数据，建议补充 E2E 测试
- 瀑布列布局的优化效果主要通过视觉判断
- 可以配合 Lighthouse 工具获得综合评分
- 不需要设置定时任务，按需手动执行
