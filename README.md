# ortools-cpsat

給 AI agent（Claude Code、Codex 等支援 [Agent Skills](https://agentskills.io/) 標準的工具）使用的 Google OR-Tools CP-SAT 限制式規劃 skill。所有解都經過不依賴模型的獨立驗證器檢查，並以測試確認。

本 skill 原本放在 [cmh3601/MCDM-Skill](https://github.com/cmh3601/MCDM-Skill)，已獨立成這個 repo；多準則決策的部分仍留在 MCDM-Skill。

## 功能

- **Job-shop 排程**（`scripts/jobshop_cpsat.py`）：interval 變數、機台 no-overlap、makespan 目標；可用 SPT／LPT／MWKR／FIFO 派工法則或外部排程（例如 DRL 策略）當 warm start；可只評估給定排程；附獨立驗證器。
- **不等面積設施佈局**（`scripts/layout_cpsat.py`）：NoOverlap2D、90 度旋轉、障礙物（柱子、走道、碼頭）、間距、鄰近（A 關係）與隔離（X 關係）限制、流量加權直角距離目標、SVG 輸出。
- **CP + 深度強化學習混合**：`--hint-file`（DRL 結果當初始解）、`--fix-hint`（只評估 DRL 佈局）、`--relax`（由策略決定放開哪些部門，其他固定，即 learned LNS）。
- **參考文件**：建模樣式、求解參數與可重現性、CP + DRL 架構與公平比較的實驗設計檢查清單。

## 驗證

12 個測試：

- ft06（Fisher & Thompson 6×6）必須得到已知最佳 makespan 55。
- 小型佈局（含障礙物與隔離限制）的最佳值與暴力窮舉一致。
- 派工法則、固定 hint、單執行緒加 `max_deterministic_time` 的重現性、驗證器能抓到重疊與先後順序違規。

## 安裝

需要 Python ≥ 3.10 與 ortools ≥ 9.10（測試版本 9.15）。

```bash
git clone https://github.com/cmh3601/ortools-cpsat.git
```

```bash
cp -R ortools-cpsat/skills/ortools-cpsat ~/.claude/skills/
```

```bash
cp -R ortools-cpsat/skills/ortools-cpsat ~/.codex/skills/
```

或使用 skills 安裝工具：

```bash
npx skills add cmh3601/ortools-cpsat
```

Python 套件：

```bash
uv venv && uv pip install ortools pytest
```

## 使用

安裝後直接用自然語言描述任務，例如：

- 「用 CP-SAT 建 flexible job shop 模型，以 DRL 產生的排程當 hint，報告與最佳下界的 gap」
- 「這個零售佈局，固定其他區域，只放開 Office 和 Returns 重新最佳化」

也可以直接執行：

```bash
python skills/ortools-cpsat/scripts/jobshop_cpsat.py skills/ortools-cpsat/data/ft06.txt --hint spt
```

```bash
python skills/ortools-cpsat/scripts/layout_cpsat.py skills/ortools-cpsat/examples/layout_8.json --svg layout.svg
```

## 測試

```bash
python -m pytest skills -q
```

GitHub Actions 設定放在 [`ci/github-actions-tests.yml`](ci/github-actions-tests.yml)。要啟用時，在 GitHub 網頁上新增 `.github/workflows/tests.yml` 並貼上內容（用命令列推送需要具備 `workflow` 權限的 token）。

## 結構

```
skills/ortools-cpsat/
  SKILL.md
  scripts/    jobshop_cpsat.py, layout_cpsat.py
  data/       ft06.txt
  examples/   layout_8.json
  references/ modeling-patterns.md, solver-and-reproducibility.md, cp-drl-hybrid.md
  tests/      test_cpsat_examples.py
```

## 授權

MIT，見 [LICENSE](LICENSE)。
