# 头晕记录 - APK 打包说明

## 文件说明

| 文件 | 用途 |
|---|---|
| `main.py` | Flet 移动端应用入口（打包 APK 用） |
| `app.py` | Streamlit 桌面版（电脑浏览器用） |
| `db.py` | 数据库模块（两个版本共用） |
| `requirements.txt` | 依赖列表 |

## 方式一：本地电脑打包 APK（需要 Android Studio）

### 1. 安装依赖

确保已安装：
- Python 3.9+
- Java JDK 17
- Android Studio（用于 Android SDK）
- Flutter SDK

在终端执行：

```bash
# Windows (Git Bash)
source .venv/Scripts/activate
HTTP_PROXY="" HTTPS_PROXY="" pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export ANDROID_HOME="$HOME/AppData/Local/Android/Sdk"
export JAVA_HOME="/c/Program Files/Java/jdk-17"
export PATH="$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools"
```

### 3. 打包 APK

```bash
flet build apk --project "头晕记录" --product "头晕记录"
```

打包完成后，APK 文件在 `build/apk/` 目录下。

## 方式二：GitHub Actions 在线打包（推荐，无需本地环境）

### 1. 创建 GitHub 仓库

将本项目的所有文件 push 到一个 GitHub 仓库。

### 2. 创建打包工作流

在仓库中创建 `.github/workflows/build-apk.yml`：

```yaml
name: Build APK

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Setup Java
        uses: actions/setup-java@v4
        with:
          distribution: "temurin"
          java-version: "17"

      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: "3.24.0"

      - name: Install dependencies
        run: |
          pip install flet

      - name: Build APK
        run: |
          flet build apk --project "头晕记录" --product "头晕记录"

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: dizziness-apk
          path: build/apk/*.apk
```

### 3. 触发打包

Push 代码到 GitHub 后，在 Actions 页面点击运行工作流。等待约 10-15 分钟后，即可下载 APK 文件。

## 方式三：手机直接运行（最简单，不打包 APK）

在 Android 手机上安装 **Pydroid 3** 应用，然后：

1. 打开 Pydroid 3
2. 将 `main.py` 和 `db.py` 复制到手机
3. 在 Pydroid 3 中打开 `main.py`
4. 点击菜单 -> 安装依赖，输入：`flet plotly pandas`
5. 点击运行按钮
6. 应用会在手机浏览器中打开（地址显示在日志中）

## 运行桌面版测试

```bash
source .venv/Scripts/activate
HTTP_PROXY="" HTTPS_PROXY="" flet run main.py
```

## 数据说明

所有记录保存在本地 `dizziness_records.db` 文件中。打包成 APK 后，数据会保存在应用私有目录中。
