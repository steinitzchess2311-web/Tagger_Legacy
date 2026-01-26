# Superchess Predictor 2.1

前后端分离版本，用于基于 FEN 预测不同棋手最可能的走法。

## 目录结构
```
superchess_predictor/
  backend/
    api.py
    engine_utils.py
    tagger_utils.py
    predictor.py
    file_utils.py
    requirements.txt
  frontend/
    app.py
    requirements.txt
  reports/
    universal_*.json
```

## 启动后端
```
cd backend
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

## 启动前端
```
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## 使用说明
1. 前端输入 FEN（无需输入 moves）。
2. 点击 “Analyze via API”。
3. 后端会调用 Stockfish（默认 `/usr/local/bin/stockfish`），获取前 7 手，打标签并计算每位棋手概率。
4. 前端展示各棋手 Top5 预测。

## 自定义引擎路径
前端框中的 `Engine path` 可填写自定义 Stockfish 路径；留空则使用默认设置。

## 健康检查
后端提供 `/health`，可快速检测服务状态。

## 注意事项
- `reports/` 中的 `universal_*_summary.json` 已预置四位棋手数据，可自行扩展。
- 如需缓存/性能优化，可在 backend 模块中扩展。
