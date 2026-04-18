# NEKOLOG-F29

NEKOLOG-F29 is a Python-based utility designed for organizing, extracting, and visualizing GPS log files. It features a lightweight, CLI-focused design, prioritizing field practicality over a complex GUI.

「ネコログF29」は、ログファイルの整理・抽出・可視化を目的としたPythonツールです。現場での実用性と軽量性を重視し、シンプルな構成で動作します。

## Features (特徴)

* **Log Organization:** Automatically organizes log files within specified folders. (ログファイルの自動整理)
* **Smart Extraction:** Extracts and summarizes essential data from raw logs. (必要な情報だけを抽出・集約)
* **Lightweight:** Minimal dependencies, primarily using Python standard libraries. (標準ライブラリ中心の軽量動作)
* **Drift Filtering:** Optimized for realistic path visualization by processing GPS noise. (GPSの揺らぎを処理し、リアルな動線を可視化)

## Requirements (必要環境)

* Python 3.10+
* OS: Windows / macOS / Linux

## Usage (使い方)

1. **Clone or Download:** Get the repository to your local machine.
2. **Configure:** Edit `config.json` if necessary to match your environment.
3. **Run:** Execute the script via command line:
   ```bas

   Project Structure (ファイル構成)
nekolog_f29.py: Main script

config.json: Configuration settings

dist/: Executable builds (for Windows)

License (ライセンス)
This project is licensed under the MIT License.
